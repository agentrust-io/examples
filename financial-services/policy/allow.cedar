// Cedar policy bundle for EU credit risk agent
// version: credit-risk-v4.2
// author: compliance@bank.eu

// Rule 1: Permit the credit-risk-analyst workflow to call any approved tool.
permit (
  principal,
  action == Action::"tool_call",
  resource
) when {
  context.workflow_id == "credit-risk-analyst"
};

// Rule 2: Advisory forbid on large credit recommendations (> 500,000 EUR).
// In advisory enforcement_mode this logs the violation and adds a TRACE annotation
// rather than hard-blocking the call.  A human reviewer must approve before
// any downstream disbursement system will accept the recommendation.
forbid (
  principal,
  action == Action::"tool_call",
  resource == Tool::"finance.risk_report_writer"
) when {
  context.amount_eur > 500000
} advice {
  "reason": "human-review-required",
  "escalation_threshold_eur": 500000
};

// Rule 3: Deny confidential tool calls if the session sensitivity has been
// downgraded to "public".  This prevents accidental data-class mismatch.
forbid (
  principal,
  action == Action::"tool_call",
  resource
) when {
  context.session_max_sensitivity == "public" &&
  resource.compliance_domain == "confidential"
};

// Rule 4: Catch-all permit — any action not matched by a forbid above is allowed.
permit (
  principal,
  action,
  resource
);
