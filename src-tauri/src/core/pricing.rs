use std::collections::HashMap;

use super::models::{CostKind, TokenUsage, UsageCost};

#[derive(Clone, Debug)]
pub struct ModelPricing {
    pub input_per_million: f64,
    pub output_per_million: f64,
    pub cached_input_per_million: Option<f64>,
}

pub struct PricingCatalog {
    version: &'static str,
    models: HashMap<&'static str, ModelPricing>,
}

impl Default for PricingCatalog {
    fn default() -> Self {
        Self {
            version: "2026-11-verified-required",
            models: HashMap::new(),
        }
    }
}

impl PricingCatalog {
    pub fn with_models(version: &'static str, models: HashMap<&'static str, ModelPricing>) -> Self {
        Self { version, models }
    }

    pub fn estimate(&self, model: &str, usage: &TokenUsage) -> UsageCost {
        let Some(pricing) = self.models.get(model) else {
            return UsageCost::unavailable();
        };
        let uncached = usage.input.saturating_sub(usage.cached_input) as f64;
        let cached_rate = pricing
            .cached_input_per_million
            .unwrap_or(pricing.input_per_million);
        let amount = uncached / 1_000_000.0 * pricing.input_per_million
            + usage.cached_input as f64 / 1_000_000.0 * cached_rate
            + usage.output as f64 / 1_000_000.0 * pricing.output_per_million;
        UsageCost {
            amount_usd: Some((amount * 10_000.0).round() / 10_000.0),
            kind: CostKind::ApiEquivalentEstimate,
            pricing_version: Some(self.version.into()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::models::DataSource;

    #[test]
    fn missing_price_is_unavailable_instead_of_zero() {
        let usage = TokenUsage {
            total: 100,
            source: DataSource::LocalUsageLogs,
            ..Default::default()
        };
        assert_eq!(
            PricingCatalog::default()
                .estimate("unknown", &usage)
                .amount_usd,
            None
        );
    }

    #[test]
    fn calculates_api_equivalent_cost_without_double_counting_cache() {
        let catalog = PricingCatalog::with_models(
            "test",
            HashMap::from([(
                "model",
                ModelPricing {
                    input_per_million: 2.0,
                    output_per_million: 8.0,
                    cached_input_per_million: Some(0.5),
                },
            )]),
        );
        let usage = TokenUsage {
            input: 1_000_000,
            output: 500_000,
            cached_input: 200_000,
            total: 1_500_000,
            source: DataSource::LocalUsageLogs,
            ..Default::default()
        };
        assert_eq!(catalog.estimate("model", &usage).amount_usd, Some(5.7));
    }
}
