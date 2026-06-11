// Cedar policy bundle for Acme Corp tenant
// version: acme-corp-v1.0
//
// Acme Corp runs the runtime in ADVISORY enforcement mode (see
// cmcp-config-acme-corp.yaml): a matched forbid is logged in the audit
// chain and surfaced as would_have_denied + advice in the response
// metadata, but the call is not blocked.

// Rule 1: permit all catalog tools.
permit (principal, action, resource);

// Rule 2: user data export should carry a GDPR Article 6 justification.
// Advisory: flagged for DPO review, not blocked.
@id("gdpr-justification-missing")
@reason("gdpr-justification-missing")
@regulation("gdpr-art-6")
forbid (
  principal,
  action == Action::"Saas.userDataExport",
  resource
) when {
  !(context.arguments has gdpr_justification) ||
  context.arguments.gdpr_justification == ""
};
