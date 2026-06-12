// Cedar policy bundle for Globex Financial tenant
// version: globex-financial-v3.2
//
// Globex Financial runs in ENFORCING mode with no catch-all permit:
// anything not explicitly permitted is denied (Cedar default-deny).
// The workflow_id is supplied by the agent via the _cmcp request metadata.

// Rule 1: any workflow may run read-only analytics queries.
permit (
  principal,
  action == Action::"Saas.analyticsQuery",
  resource
);

// Rule 2: only the data-compliance workflow may export user data.
permit (
  principal,
  action == Action::"Saas.userDataExport",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "data-compliance-workflow"
};

// Rule 3: only the admin workflow may update configuration.
permit (
  principal,
  action == Action::"Saas.configUpdate",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "admin-workflow"
};

// Rule 4: explicit annotated forbid for data export outside the
// data-compliance workflow, so the deny carries structured advice.
@id("export-requires-compliance-workflow")
@reason("export-requires-data-compliance-workflow")
@regulation("gdpr-art-6")
forbid (
  principal,
  action == Action::"Saas.userDataExport",
  resource
) when {
  !(context has workflow_id) ||
  context.workflow_id != "data-compliance-workflow"
};

// Rule 5: explicit annotated forbid for config updates outside the
// admin workflow.
@id("config-update-requires-admin-workflow")
@reason("config-update-requires-admin-workflow")
forbid (
  principal,
  action == Action::"Saas.configUpdate",
  resource
) when {
  !(context has workflow_id) ||
  context.workflow_id != "admin-workflow"
};
