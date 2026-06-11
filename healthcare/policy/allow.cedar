// Cedar policy bundle for hospital clinical decision support agent
// version: clinical-hipaa-v2.1
// author: compliance@hospital.example
//
// Action names follow the cMCP convention: tool_name converted to
// PascalCase per underscore segment, e.g. ehr.treatment_plan_writer
// becomes Action::"Ehr.treatmentPlanWriter".

// Rule 1: the attested catalog is the allow-list; permit catalog tools and
// let the forbid rules below carry the compliance constraints.
permit (principal, action, resource);

// Rule 2: EU AI Act Article 14 human oversight. Treatment plan writes for
// high-risk patients are blocked until an attending physician approves.
// The annotations are returned to the caller as structured advice on deny.
@id("hitl-high-risk")
@reason("human-review-required")
@regulation("eu-ai-act-art-14")
@reviewer_role("attending-physician")
forbid (
  principal,
  action == Action::"Ehr.treatmentPlanWriter",
  resource
) when {
  context.arguments has patient_risk_category &&
  context.arguments.patient_risk_category == "high"
};

// Rule 3: HIPAA PHI may only flow through an attested runtime.
@id("require-attested-runtime")
@reason("attested-runtime-required")
@regulation("hipaa-164-312")
forbid (
  principal,
  action,
  resource
) when {
  context.compliance_domain == "hipaa_phi" &&
  context.attestation_platform == "unknown"
};
