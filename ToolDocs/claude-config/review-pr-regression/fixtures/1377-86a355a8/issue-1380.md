# #1380: [Task](aurora): Create an AI agent skill for scaffolding new OpenStack resources

State: CLOSED · https://github.com/cobaltcore-dev/aurora-dashboard/issues/1380

**Task Description**

Adding a new OpenStack resource to Aurora (BFF, UI, tests, docs, issues, PR, changeset) follows the same steps every time. The Neutron Routers feature showed that most of the effort goes into repeating established patterns and avoiding the same pitfalls, not into resource-specific logic.

Create a skill for AI coding agents (e.g. Claude Code in VS Code) that guides this process end to end, so new resources ("layouts") are built consistently with the existing code and team conventions.

The skill should:

- **Collect the inputs up front:** epic text, API reference, design screenshots / Figma, list columns, details sections, and the UI mode (read-only or full CRUD).
- **Run in three phases, pausing for review after each one:**
  1. **BFF:** types, helpers, shared utilities (if needed), router, tests, documentation.
  2. **UI:** navigation entry and service card, routing (list and details), components, tests. Supports read-only and full CRUD modes.
  3. **Finalization:** GitHub task issues, PR title and description, changeset.
- **Allow running a single phase on its own.**
- **Reuse the existing implementations in the repository as references,** instead of duplicating code inside the skill.
- **Run the same checks as CI** before a phase is reported as done.

**Sub-tasks**

- [ ] Define the skill structure (main instructions, per-phase references, templates, helper scripts)
- [ ] Intake: questionnaire and the plan confirmation step
- [ ] Phase 1 guide: BFF conventions, tests and docs
- [ ] Phase 2 guide: UI conventions for read-only and full CRUD modes, tests
- [ ] Phase 3 guide and templates: issues, PR, changeset, commit conventions
- [ ] Known pitfalls collected from the Routers feature
- [ ] Verification script aligned with CI checks (typecheck, lint, format, tests, i18n, build, PR title)
- [ ] Try the skill on the next resource and refine it based on the results

**Acceptance Criteria**

- [ ] The skill can be installed locally (e.g. in the user's agent skills folder) and is picked up automatically by the agent.
- [ ] Starting the skill collects all required inputs before any code is written.
- [ ] Each phase produces code, docs and texts that follow the existing patterns and the team's review guidelines (`.github/copilot-instructions.md`, issue and PR templates, commitlint rules).
- [ ] Read-only and full CRUD UI modes are both supported.
- [ ] Each phase ends with a summary, verification results and proposed commit messages, and waits for confirmation.
- [ ] The skill has been used successfully for at least one new resource.

**Out of Scope**

- Changes to existing resources beyond what the reference patterns require.
- Fully unattended generation without human review between phases.

**Related Issues**

- Builds on: Neutron Routers epic (#<routers-epic-number>)

**Additional Context**

The Routers implementation serves as the primary reference for the read-only mode. Floating IPs and Security Groups serve as references for full CRUD.
