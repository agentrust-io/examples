// Cedar policy bundle for EU credit risk agent
// version: credit-risk-v4.2
// author: compliance@bank.eu
//
// Action names follow the cMCP convention: tool_name converted to
// PascalCase per underscore segment, e.g. finance.risk_report_writer
// becomes Action::"Finance.riskReportWriter".
//
// There is deliberately NO catch-all permit: anything not explicitly
// permitted below is denied (Cedar default-deny). The workflow_id is
// supplied by the agent via the _cmcp request metadata; calls without
// it are denied.

// Rule 1: the credit-risk-analyst workflow may read client documents.
permit (
  principal,
  action == Action::"Finance.documentReader",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "credit-risk-analyst"
};

// Rule 2: the credit-risk-analyst workflow may query credit bureaus.
permit (
  principal,
  action == Action::"Finance.creditScoreLookup",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "credit-risk-analyst"
};

// Rule 3: the credit-risk-analyst workflow may write risk reports.
// Subject to the large-exposure forbid below.
permit (
  principal,
  action == Action::"Finance.riskReportWriter",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "credit-risk-analyst"
};

// Rule 4: large-exposure escalation (MiFID II Art. 25).
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

// Rule 5: confidential financial data may only flow through an attested
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
