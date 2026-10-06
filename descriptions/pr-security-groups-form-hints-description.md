# Summary

Addresses the review comment:

> Show validation information or other important information (e.g. what happens if a field is left empty) on form inputs in help hints, cross check with Elektra

Every input in Create/Edit Security Group, Add Rule and Share Security Group now has a help hint with its limits and what an empty value means; placeholders are removed. Errors behave the same in all four modals: shown when a field is left, hidden while it is edited, with the confirm button disabled while the form is invalid.

The cross-check with Elektra and Neutron found a few things the hints would otherwise describe wrongly; they are fixed here:

- **An empty Remote Security Group created a rule open to everyone.** The field is now required.
- **A rule with an IPv6 CIDR could not be created.** The hidden ethertype was forced to IPv4. It is now taken from the CIDR, as in Horizon. Only a security group remote asks for the IP version.
- **The current group could not be chosen as the remote.** It is back in the list as `<name> (this group)`.
- **A failed create closed the modal and lost the input.** The modal now stays open and shows the error.
- **The rules table had no Remote column.** Added: CIDR, group name or `Any`. The delete dialog and the rules search use the same value.

# Changes Made

## Client

- **`securityGroupValidation.ts`** (new): name and description validation for Create/Edit: required name, 255-character limits, reserved `default`.
- **`CreateSecurityGroupModal.tsx`, `EditSecurityGroupModal.tsx`, `AddRuleModal.tsx`, `AddRBACPolicyModal.tsx`**: help hints and the common modal pattern (on-blur errors, disabled confirm, in-form error message).
- **`AddRuleModal/validation/fieldErrors.ts`** (new): when a field's error is visible in Add Rule.
- **`AddRuleModal/validation/formSchema.ts`**:
  - Remote Security Group required;
  - protocol name or number 0-255;
  - description limit;
  - no CIDR/ethertype mismatch check.
- **`AddRuleModal/sections/*`**: hints instead of placeholders; preset ports shown read-only; ICMP type/code only for Custom ICMP and Other Protocol.
- **`ruleRemote.ts`** (new), **`SecurityGroupRulesTable.tsx`**, **`DeleteRuleDialog.tsx`**, **`useSecurityGroupDetails.ts`**: Remote column, delete dialog line and search.
- **`SecurityGroupsList.tsx`**: lets a failed create reject so the modal stays open.

## Tests

- Hints, error visibility, validation rules, IPv6/IPv4 ethertype, required remote group, the Remote column and search.
- 5870 tests pass; `typecheck`, `lint`, `format:check` and `check-i18n` are clean.

# Testing Instructions

1. `pnpm i`
2. `pnpm run test`
3. Network → Security Groups: open Create, Add Rule and Share, and check the hints and errors.
4. In Add Rule:
   - choose Remote = Security Group without a group: Add Rule stays disabled;
   - add a rule with CIDR `::/0`: it is created as IPv6.
5. Check that the rules table shows a Remote column.

# Checklist

- [x] I have performed a self-review of my code.
- [x] I have commented my code, particularly in hard-to-understand areas.
- [x] I have added tests that prove my fix is effective or that my feature works.
- [x] New and existing unit tests pass locally with my changes.
- [x] I have made corresponding changes to the documentation (if applicable).
- [x] My changes generate no new warnings or errors.
