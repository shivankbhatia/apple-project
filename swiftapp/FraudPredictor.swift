import CoreML
import Foundation

/// Wraps the CoreML model. Xcode auto-generates a `FraudModel` class (with
/// `FraudModelInput`/`FraudModelOutput`) from FraudModel.mlmodel the moment
/// you drag it into the project — no manual codegen needed.
///
/// Feature names below MUST match FEATURE_NAMES in convert_model.py exactly,
/// including order — that's the schema contract between Python and Swift.
struct FraudPredictor {
    private let model: FraudModel

    init() {
        // `try!` here is intentional for a portfolio project: if the model
        // fails to load, that's a build-config bug you want to see immediately,
        // not something to silently swallow. Swap for `try?` + error UI if you
        // want production-style graceful degradation.
        self.model = try! FraudModel(configuration: MLModelConfiguration())
    }

    /// Runs inference for one click batch entirely on-device.
    /// Returns fraud probability in [0, 1].
    func predict(_ batch: ClickBatch) -> Double {
        let input = FraudModelInput(
            click_velocity: batch.clickVelocity,
            fingerprint_entropy: batch.fingerprintEntropy,
            click_to_conv_ratio: batch.clickToConvRatio,
            geo_mismatch: batch.geoMismatch,
            time_to_click_ms: batch.timeToClickMs,
            ip_reuse_rate: batch.ipReuseRate
        )

        guard let output = try? model.prediction(input: input) else {
            return 0.0
        }

        // XGBoost classifier output in CoreML exposes classProbability as
        // [Int64: Double] — class 1 is "fraud".
        return output.classProbability[1] ?? 0.0
    }
}
