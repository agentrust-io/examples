// Cedar policy bundle for hospital clinical decision support agent
// version: clinical-hipaa-v2.1
// author: compliance@hospital.example
//
// Action names follow the cMCP convention: tool_name converted to
// PascalCase per underscore segment, e.g. ehr.treatment_plan_writer
// becomes Action::"Ehr.treatmentPlanWriter".
//
// There is deliberately NO catch-all permit: anything not explicitly
// permitted below is denied (Cedar default-deny). The workflow_id is
// supplied by the agent via the _cmcp request metadata; calls without
// it are denied.

// Rule 1: the clinical-decision-support workflow may look up patient records.
permit (
  principal,
  action == Action::"Ehr.patientRecordLookup",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "clinical-decision-support"
};

// Rule 2: the clinical-decision-support workflow may run differential diagnosis.
permit (
  principal,
  action == Action::"Ehr.clinicalDecisionSupport",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "clinical-decision-support"
};

// Rule 3: the clinical-decision-support workflow may write treatment plans.
// Subject to the HITL forbid below.
permit (
  principal,
  action == Action::"Ehr.treatmentPlanWriter",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "clinical-decision-support"
};

// Rule 4: EU AI Act Article 14 human oversight. Treatment plan writes for
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

// Rule 5: HIPAA PHI may only flow through an attested runtime.
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
