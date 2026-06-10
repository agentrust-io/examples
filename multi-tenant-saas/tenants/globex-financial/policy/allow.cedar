// Cedar policy bundle for Globex Financial tenant
// version: globex-financial-v3.2
// Financial services tenant — strict GDPR compliance required.
// User data export is only permitted for the data-compliance-workflow.
// Config updates are only permitted for the admin-workflow.

// Rule 1: Permit data-compliance-workflow to export user data.
permit (
  principal,
  action == Action::"tool_call",
  resource == Tool::"saas.user_data_export"
) when {
  context.workflow_id == "data-compliance-workflow"
};

// Rule 2: Permit admin-workflow to update configuration.
permit (
  principal,
  action == Action::"tool_call",
  resource == Tool::"saas.config_update"
) when {
  context.workflow_id == "admin-workflow"
};

// Rule 3: Permit any workflow to run read-only analytics queries.
permit (
  principal,
  action == Action::"tool_call",
  resource == Tool::"saas.analytics_query"
);

// Rule 4: Deny user data export for all other workflows (hard deny, no advice).
// Financial services regulations require explicit GDPR Article 6 lawful basis
// per request. Only the data-compliance-workflow is authorised to invoke this.
forbid (
  principal,
  action == Action::"tool_call",
  resource == Tool::"saas.user_data_export"
) when {
  context.workflow_id != "data-compliance-workflow"
};

// Rule 5: Advisory forbid on config updates outside the admin-workflow.
// Logged for the security team; does not block.
forbid (
  principal,
  action == Action::"tool_call",
  resource == Tool::"saas.config_update"
) when {
  context.workflow_id != "admin-workflow"
} advice {
  "reason": "config-update-requires-admin-workflow",
  "action": "advisory-log-and-notify-security"
};
