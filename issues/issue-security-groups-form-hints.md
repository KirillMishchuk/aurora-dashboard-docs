# [Feature](network): help hints and validation on Security Groups form inputs

**Description**

> Show validation information or other important information (e.g. what happens if a field is left empty) on form inputs in help hints, cross check with Elektra

Add a help hint to every input in the Security Groups forms (Create/Edit Security Group, Add Rule, Share Security Group) with its validation rules and what an empty value means. Cross-check the fields against Elektra.

**Problem Statement**

Most fields have no hints. What there is lives in placeholders, which disappear as the user types. Limits such as the 255-character name or the reserved name `default` surface only as backend errors. What an empty field does is not shown anywhere. For example, an empty CIDR allows any IPv4 address, and an empty Remote Security Group created a rule open to everyone.

**Proposed Solution**

- A `helptext` on every input instead of placeholders.
- Client-side validation matching Neutron, with the same error behaviour in all four modals.
- Fix what the cross-check turns up. For example, an empty Remote Security Group must not be accepted, and the rules table needs a Remote column.
