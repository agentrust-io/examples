// Cedar policy bundle for hospital clinical decision support agent
// version: clinical-hipaa-v2.1
// author: compliance@hospital.example

// Rule 1: Permit the clinical-decision-support workflow to call approved EHR tools.
permit (
  principal,
  action == Action::"tool_call",
  resource
) when {
  context.workflow_id == "clinical-decision-support"
};

// Rule 2: Advisory forbid on treatment plan writes for high-risk patients.
// EU AI Act Article 14 requires human oversight for high-risk AI system outputs
// in healthcare settings.  When patient_risk_category == "high", the treatment
// plan must be reviewed and approved by a clinician before it takes effect.
// In enforcing mode this blocks the write and returns a 403 with the HITL payload.
forbid (
  principal,
  action == Action::"tool_call",
  resource == Tool::"ehr.treatment_plan_writer"
) when {
  context.patient_risk_category == "high"
} advice {
  "reason": "human-review-required",
  "regulation": "eu-ai-act-art-14",
  "reviewer_role": "attending-physician"
};

// Rule 3: Deny confidential tool calls if the session sensitivity has been
// downgraded to "public".  Prevents accidental HIPAA PHI leakage.
forbid (
  principal,
  action == Action::"tool_call",
  resource
) when {
  context.session_max_sensitivity == "public" &&
  resource.compliance_domain == "hipaa_phi"
};

// Rule 4: Catch-all permit — any call not matched by a forbid above is allowed.
permit (
  principal,
  action,
  resource
);
