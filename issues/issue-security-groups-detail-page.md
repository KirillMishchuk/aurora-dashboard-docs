# [Task](network): Security Group detail page layout and Juno components

**Task Description**

Align the Security Group detail page with the Juno design system: heading structure, description list layout, button variants and tabs.

**Sub-tasks**

- [ ] Add an `h2` "General Information" above the group's description list (the page title stays `h1`).
- [ ] Order the left column of the description list as Name, Description, ID, Tags.
- [ ] `TwoColumnDescriptionList`: remove the `grid grid-cols-2` classes from the `Stack` and let its flexbox lay out the columns, keeping them equal width.
- [ ] `TwoColumnDescriptionList`: stop stretching the shorter column to the height of the taller one.
- [ ] Use the default button variant for "Add Rule" and "Share Security Group".
- [ ] Replace the custom `Stack` tabs (Rules, RBAC Policies) with Juno `TabNavigation`.
- [ ] Switch back to the Rules tab when the RBAC Policies tab disappears while it is open. Today the RBAC content stays on screen with no tab selected.

**Related Issues**

**Additional Context**

`TwoColumnDescriptionList` is shared, so the two layout fixes also apply to the Floating IP and Image detail pages.
