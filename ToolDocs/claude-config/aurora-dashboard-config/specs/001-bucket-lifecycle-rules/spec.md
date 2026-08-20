# Feature Specification: Ceph Bucket Lifecycle Rules

**Feature Branch**: `001-bucket-lifecycle-rules`

**Created**: 2026-08-04

**Status**: Draft

**Input**: User description: "Check the implementation of Storage Ceph. I need to add a new feature. this is the link to the whole epic and this is what we need to implement https://github.com/cobaltcore-dev/aurora-dashboard/issues/608 — Section 13: Lifecycle Rules (P3). Automate object expiration and transitions. BFF: Define Zod schema for lifecycle rule; Implement buckets.getLifecycle / buckets.setLifecycle / buckets.deleteLifecycle. UI: Create lifecycle rule list with add/edit/delete."

## Clarifications

### Session 2026-08-04

- Q: Must a lifecycle rule's name be unique within a bucket, or can multiple rules share the same name? → A: Name must be unique per bucket; duplicate names are rejected client-side before save
- Q: Should the incomplete-multipart-upload abort action use the rule's own key-prefix scope, or apply bucket-wide regardless of the rule's prefix? → A: Multipart-abort action is scoped by the same key-prefix as the rest of the rule
- Q: Can users manually reorder lifecycle rules in the list, or is order fixed with no reordering control? → A: No manual reordering; order is not evaluation-significant (each rule acts independently), list is just stably sorted for display
- Q: Should the UI proactively fetch/enforce the storage backend's max-rules-per-bucket limit before save, or rely on the backend's rejection at save time? → A: UI relies on the backend's rejection at save time and surfaces that error clearly, without proactively tracking the limit
- Q: Should the number-of-days fields have an enforced upper bound, or is any positive whole number accepted? → A: No upper bound beyond "positive whole number"; backend rejects unsupported values

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View a bucket's lifecycle rules (Priority: P1)

A project member managing a Ceph bucket opens the bucket's lifecycle settings and sees the full list of currently configured lifecycle rules — including rules that may have been set up outside the dashboard — with each rule's name, enabled/disabled status, scope, and configured actions (expiration, transition, etc.).

**Why this priority**: Without visibility into existing rules, users cannot safely audit, trust, or build on top of any automation already governing their data. This is the minimum needed to make the feature useful and is a prerequisite for every other story.

**Independent Test**: Can be fully tested by opening a bucket that already has a lifecycle configuration (set via any tool) and confirming every rule and its details are displayed accurately, and by opening a bucket with no configuration and confirming an empty state is shown.

**Acceptance Scenarios**:

1. **Given** a bucket with two lifecycle rules configured, **When** the user opens the bucket's lifecycle view, **Then** both rules are listed with their name, status, scope, and actions visible.
2. **Given** a bucket with no lifecycle rules, **When** the user opens the bucket's lifecycle view, **Then** the system clearly indicates no rules are configured.
3. **Given** a bucket whose lifecycle configuration was created by a tool other than this dashboard, **When** the user opens the bucket's lifecycle view, **Then** the existing rules are displayed accurately rather than appearing empty or causing an error.

---

### User Story 2 - Create a lifecycle rule (Priority: P2)

A project member wants objects in a bucket to be automatically deleted or moved to a different storage tier after a certain amount of time, without manual intervention. They add a new rule scoped to a key prefix, choose one or more actions (expire current objects after N days, transition current objects after N days, expire/transition previous versions, or clean up abandoned multipart uploads), and save it.

**Why this priority**: This is the core value of the feature — automating expiration/transition — but it depends on Story 1 existing so the user can see what they're adding to.

**Independent Test**: Can be fully tested by creating a rule with an expiration action on a test bucket, saving it, and confirming it appears correctly in the rule list (Story 1) and is applied by the storage backend.

**Acceptance Scenarios**:

1. **Given** a bucket with no lifecycle rules, **When** the user creates a rule that expires objects under a given prefix after 30 days, **Then** the rule is saved and appears in the rule list with the correct prefix and expiration period.
2. **Given** a bucket with versioning enabled, **When** the user creates a rule that also expires noncurrent (previous) versions after a set number of days, **Then** the rule is saved with both current- and noncurrent-version actions distinguished from each other.
3. **Given** a user attempting to save a rule with no actions selected, **When** they submit the form, **Then** the system blocks the save and explains that at least one action is required.
4. **Given** a user configuring a transition action on a cluster with no alternate storage classes available, **When** they attempt to add the transition action, **Then** the system clearly communicates that transitions are unavailable rather than allowing a save that would fail later.

---

### User Story 3 - Edit and delete existing lifecycle rules (Priority: P3)

A project member needs to adjust an existing rule (e.g., change the retention period, disable it temporarily, narrow its scope) or remove a rule that's no longer needed.

**Why this priority**: Editing and deletion are necessary for the feature to be maintainable long-term, but the feature already delivers value once users can view (Story 1) and create (Story 2) rules; correcting or removing rules is a secondary but expected capability.

**Independent Test**: Can be fully tested by editing a previously created rule's expiration period and confirming the change is reflected, and separately by deleting a rule and confirming it's removed from the list.

**Acceptance Scenarios**:

1. **Given** an existing enabled rule, **When** the user disables it, **Then** the rule remains listed but shown as disabled and no longer acts on new objects.
2. **Given** an existing rule, **When** the user changes its expiration period and saves, **Then** the updated period is reflected immediately in the rule list.
3. **Given** an existing rule, **When** the user chooses to delete it, **Then** the system asks for confirmation before removing it, since expiration rules can permanently delete data once objects age past the threshold.
4. **Given** a rule that was created outside the dashboard using a filter condition the UI doesn't support editing (e.g., an object-tag filter), **When** the user opens it for editing, **Then** the system does not silently drop or overwrite the unsupported condition.

---

### Edge Cases

- What happens when a user tries to create a rule whose scope (prefix) exactly overlaps with an existing rule's scope? The system allows it (multiple rules may target overlapping scopes, consistent with standard object storage lifecycle behavior) but the rule list should make it easy to spot overlapping scopes.
- How does the system handle a bucket that already has the maximum number of lifecycle rules supported by the storage backend? The system blocks adding further rules and explains the limit has been reached.
- What happens if a user configures noncurrent-version actions on a bucket where versioning is not enabled? The system warns that these actions will have no effect until versioning is enabled, rather than silently accepting a no-op configuration.
- What happens if the storage backend rejects a rule at save time (e.g., transient failure, invalid combination not caught by client-side validation)? The user sees a clear error and the rule list reflects the last known-good state rather than showing a rule that wasn't actually saved.
- What happens when deleting the last remaining rule on a bucket? The bucket returns to the "no rules configured" empty state from Story 1.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users with bucket-management permission MUST be able to view the list of lifecycle rules configured on a bucket, including each rule's name/identifier, enabled/disabled status, scope (key prefix), and configured actions.
- **FR-002**: The system MUST display a clear empty state when a bucket has no lifecycle rules configured.
- **FR-003**: The system MUST accurately display lifecycle rules that were configured through means other than this dashboard.
- **FR-004**: Users MUST be able to create a new lifecycle rule, specifying a name, enabled/disabled status, an optional key prefix to scope which objects it applies to, and one or more actions. Rule names MUST be unique within a bucket; the system MUST reject a duplicate name before submitting the rule to the storage backend.
- **FR-005**: The system MUST support an expiration action that automatically deletes current objects a specified number of days after creation.
- **FR-006**: The system MUST support a transition action that automatically moves current objects to a different storage class a specified number of days after creation, and MUST clearly indicate when no alternate storage class is available for transitions.
- **FR-007**: For buckets with versioning enabled, the system MUST support separate expiration and transition actions for noncurrent (previous) object versions.
- **FR-008**: The system MUST support automatically aborting incomplete multipart uploads a specified number of days after they were started, to reclaim storage from abandoned uploads, scoped by the same key-prefix as the rest of the rule.
- **FR-009**: The system MUST require at least one action to be defined before a rule can be saved, and MUST block save attempts that don't meet this requirement with a clear explanation.
- **FR-010**: The system MUST validate rule inputs (day counts must be positive whole numbers, with no client-enforced upper bound) and reject invalid configurations before submitting them to the storage backend; values the client accepts but the backend cannot support are surfaced via the backend's rejection at save time.
- **FR-011**: Users MUST be able to edit an existing rule's status, scope, and actions.
- **FR-012**: Users MUST be able to delete an existing rule, and the system MUST require confirmation before deletion given the potential for permanent, irreversible data loss once a rule takes effect.
- **FR-013**: The system MUST NOT silently discard or overwrite parts of a rule's configuration that the UI does not support editing (e.g., filter conditions set by other tools); such rules must remain visible and must not be corrupted by an edit to a different part of the same rule.
- **FR-014**: Viewing and modifying lifecycle rules MUST be restricted to users holding the same permission level already required for other bucket-configuration actions (e.g., bucket policies, versioning).
- **FR-015**: The system MUST enforce the storage backend's maximum number of lifecycle rules per bucket and inform the user when the limit is reached. The UI does not proactively track or fetch this limit; it relies on the storage backend's rejection at save time and surfaces that error to the user clearly.

### Key Entities

- **Lifecycle Rule**: An automation rule attached to a bucket. Key attributes: name/identifier (unique within the bucket), enabled/disabled status, key-prefix scope, current-version actions (expire after N days, transition to a storage class after N days), noncurrent-version actions (expire after N days, transition after N days), and an incomplete-multipart-upload abort action (after N days, scoped by the same key-prefix). A bucket's lifecycle configuration is the collection of its rules; rules act independently of one another and their relative order is not evaluation-significant, so the UI does not need manual reordering — the list is displayed in a stable order (e.g., by name).
- **Bucket**: The existing Ceph object storage container that a lifecycle configuration is attached to; a bucket has zero or many lifecycle rules.
- **Storage Class**: An existing Ceph storage tier that objects can transition into; relevant only when the underlying cluster is configured with more than one class.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can find and open a bucket's lifecycle rules within 2 clicks from the bucket detail view.
- **SC-002**: A user can create a working expiration or transition rule in under 2 minutes without needing outside help or documentation.
- **SC-003**: 100% of pre-existing lifecycle configurations (created via tools other than this dashboard) are displayed accurately and are never silently lost when a bucket is opened or one of its rules is edited.
- **SC-004**: Invalid rule configurations are caught and explained before submission, so fewer than 5% of rule save attempts are rejected by the storage backend.
- **SC-005**: Deleting a rule always requires an explicit confirmation step, resulting in zero accidental rule deletions attributable to a missing confirmation step.

## Assumptions

- Bucket versioning is already a supported, existing capability of the dashboard; this feature's noncurrent-version actions build on that existing capability rather than introducing bucket versioning itself.
- Object tagging is not currently exposed anywhere in the dashboard. This feature therefore scopes rule matching in the add/edit UI to key-prefix only; rules created externally with tag-based filters remain visible but are not editable through this UI until object tagging is supported elsewhere in the product.
- Storage-class transition actions depend on the underlying Ceph cluster having more than one storage class configured; where it doesn't, the feature communicates this rather than exposing a transition option that would fail when applied.
- Managing lifecycle rules requires the same elevated permission level already required for other bucket-configuration actions (bucket policies, versioning), consistent with existing access-control conventions in the dashboard.
- The storage backend's standard lifecycle limits (e.g., maximum rules per bucket) apply as-is; this feature does not attempt to raise or work around them.
