import json
import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

from pyflink.common import Types, WatermarkStrategy
from pyflink.datastream.connectors.base import DeliveryGuarantee
from pyflink.common.serialization import Encoder, SimpleStringSchema
from pyflink.common.time import Time
from pyflink.datastream import KeyedProcessFunction, StreamExecutionEnvironment
from pyflink.datastream.connectors.file_system import FileSink, OutputFileConfig
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.state import StateTtlConfig, ValueStateDescriptor

sys.path.insert(0, "/opt/fraud_lambda")

from features.click_features import IncrementalClickFeatures, vectorize


MODEL_DIR = Path("/opt/fraud_lambda/models")
STAGING_DIR = "/opt/fraud_lambda/data/staging"
FLAG_THRESHOLD = 0.859968


class ClickScorer(KeyedProcessFunction):
    def open(self, runtime_context):
        descriptor = ValueStateDescriptor(
            "ip_click_feature_engine",
            Types.PICKLED_BYTE_ARRAY(),
        )

        ttl = (
            StateTtlConfig.new_builder(Time.hours(2))
            .set_update_type(StateTtlConfig.UpdateType.OnCreateAndWrite)
            .set_state_visibility(
                StateTtlConfig.StateVisibility.NeverReturnExpired
            )
            .build()
        )
        descriptor.enable_time_to_live(ttl)
        self.feature_state = runtime_context.get_state(descriptor)

        with (MODEL_DIR / "click_fraud_model.pkl").open("rb") as source:
            self.model = pickle.load(source)

        with (MODEL_DIR / "feature_list.pkl").open("rb") as source:
            self.feature_order = pickle.load(source)

        stats = json.loads((MODEL_DIR / "campaign_stats.json").read_text())
        self.campaign_stats = stats["campaign"]
        self.publisher_stats = stats["publisher"]

    def process_element(self, value, ctx):
        try:
            click = json.loads(value)
        except json.JSONDecodeError:
            return

        serialized_engine = self.feature_state.value()
        if serialized_engine:
            engine = pickle.loads(serialized_engine)
        else:
            engine = IncrementalClickFeatures()

        # Keep shared batch/stream functions unchanged; Flink supplies a
        # processing-time override and uses no event-time watermarks.
        engine.campaign_stats = self.campaign_stats
        engine.publisher_stats = self.publisher_stats
        click["feature_timestamp"] = datetime.now(timezone.utc).isoformat()

        scored = engine.enrich(click)

        # Do not duplicate the batch statistics in every keyed-state record.
        engine.campaign_stats = {}
        engine.publisher_stats = {}
        self.feature_state.update(pickle.dumps(engine))

        probability = float(self.model.predict_proba([vectorize(scored)])[0][1])
        scored["fraud_probability"] = round(probability, 6)
        scored["is_flagged"] = int(probability >= FLAG_THRESHOLD)
        scored["scored_at"] = datetime.now(timezone.utc).isoformat()

        published_at = datetime.fromisoformat(
            scored["event_timestamp"].replace("Z", "+00:00")
        )
        scored_at = datetime.fromisoformat(
            scored["scored_at"].replace("Z", "+00:00")
        )
        scored["latency_ms"] = max(
            0,
            round((scored_at - published_at).total_seconds() * 1000, 3),
        )

        # Internal processing-time helper, not part of the output schema.
        scored.pop("feature_timestamp", None)
        yield json.dumps(scored)


def extract_ip(raw_json):
    return json.loads(raw_json)["ip"]


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    env.enable_checkpointing(10_000)

    env.add_jars(
        "file:///opt/flink-job/lib/flink-connector-kafka-3.0.2-1.18.jar",
        "file:///opt/flink-job/lib/kafka-clients-3.4.0.jar",
    )

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers("kafka:29092")
        .set_topics("clicks")
        .set_group_id("click-scorer-v1")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    clicks = env.from_source(
        source,
        WatermarkStrategy.no_watermarks(),
        "clicks-kafka-source",
    )

    scored = clicks.key_by(extract_ip, key_type=Types.STRING()).process(
        ClickScorer(),
        output_type=Types.STRING(),
    )

    file_sink = (
        FileSink.for_row_format(STAGING_DIR, Encoder.simple_string_encoder())
        .with_output_file_config(
            OutputFileConfig.builder()
            .with_part_prefix("scored")
            .with_part_suffix(".json")
            .build()
        )
        .build()
    )
    scored.sink_to(file_sink)

    alert_sink = (
        KafkaSink.builder()
        .set_bootstrap_servers("kafka:29092")
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic("click_alerts")
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        )
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)
        .build()
    )

    scored.filter(
        lambda raw_json: json.loads(raw_json)["is_flagged"] == 1
    ).sink_to(alert_sink)

    env.execute("click-scorer")


if __name__ == "__main__":
    main()