// Cedar policy bundle for EU credit risk agent
// version: credit-risk-v4.2
// author: compliance@bank.eu
//
// Action names follow the cMCP convention: tool_name converted to
// PascalCase per underscore segment, e.g. finance.risk_report_writer
// becomes Action::"Finance.riskReportWriter".

// Rule 1: the attested catalog is the allow-list; permit catalog tools and
// let the forbid rules below carry the compliance constraints.
permit (principal, action, resource);

// Rule 2: large-exposure escalation (MiFID II Art. 25).
// Any risk report above 500,000 EUR requires a human reviewer. The
// annotations are returned to the caller as structured advice on deny.
@id("large-exposure-hitl")
@reason("human-review-required")
@regulation("mifid-ii-art-25")
@escalation_threshold_eur("500000")
forbid (
  principal,
  action == Action::"Finance.riskReportWriter",
  resource
) when {
  context.arguments has amount_eur &&
  context.arguments.amount_eur > 500000
};

// Rule 3: confidential financial data may only flow through an attested
// runtime. attestation_platform is supplied by the gateway from the TEE
// attestation report; "unknown" means no attestation evidence is present.
@id("require-attested-runtime")
@reason("attested-runtime-required")
@regulation("dora-art-9")
forbid (
  principal,
  action,
  resource
) when {
  context.compliance_domain == "mnpi" &&
  context.attestation_platform == "unknown"
};
