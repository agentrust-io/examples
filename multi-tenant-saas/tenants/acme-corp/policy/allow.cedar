// Cedar policy bundle for Acme Corp tenant
// version: acme-corp-v1.0
// Standard SaaS tenant — all tools permitted for the analytics workflow.
// User data export requires a GDPR justification (advisory only — logged
// but not blocked, so the business can operate while the DPO reviews).

// Rule 1: Permit the analytics workflow to call any platform tool.
permit (
  principal,
  action == Action::"tool_call",
  resource
) when {
  context.workflow_id == "analytics-workflow"
};

// Rule 2: Advisory forbid on user data export without a GDPR justification.
// Logged in the TRACE record for DPO review; does not block the call.
forbid (
  principal,
  action == Action::"tool_call",
  resource == Tool::"saas.user_data_export"
) when {
  !context.has("gdpr_justification") || context.gdpr_justification == ""
} advice {
  "reason": "gdpr-justification-missing",
  "regulation": "gdpr-art-6",
  "action": "advisory-log-only"
};

// Rule 3: Catch-all permit.
permit (
  principal,
  action,
  resource
);
