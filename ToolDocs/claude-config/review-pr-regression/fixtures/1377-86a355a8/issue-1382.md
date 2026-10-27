# #1382: [Task](networking): Ports list view and details view

State: OPEN · https://github.com/cobaltcore-dev/aurora-dashboard/issues/1382

**Task Description**

Part of #816

Add a read-only Ports page to Aurora Dashboard, so users can browse a project's ports and inspect a single port. The ports list must be reusable for a "Ports" tab in the network details view (#1019). Follow the Aurora design system (juno-ui-components) and the existing list and detail page patterns.

Design reference: elektra Ports list and Port details screenshots in #816.

**Sub-tasks**

- [ ] "Ports" entry in the side navigation under Network, and a service card on the project overview (shown only when the network service is available)
- [ ] List view: table with columns Name / ID, Description, Network, Fixed IPs / Subnet, Device Owner / ID, Status; search, sorting and pagination persisted in the URL; loading, empty and error states
- [ ] Reusable list: can be scoped to a single network, in which case the Network column is hidden
- [ ] Details view: Port ID, MAC, Network, IPs (with IP version and subnet), Description, Name, Device Owner, Device ID, Created at, Updated at, Project ID, Status, Security Groups; copy-to-clipboard for IDs, IP addresses and the MAC address; loading, not-found and error states
- [ ] Component tests

**Acceptance Criteria**

- [ ] The page is reachable from the side navigation and the project overview.
- [ ] The list view shows the agreed columns for the current project, with working search, sorting and pagination.
- [ ] The list can be rendered for a single network without the Network column.
- [ ] The details view shows all fields listed above.
- [ ] Missing data (e.g. unresolvable names, ports without IPs or device) is handled gracefully.
- [ ] UI follows the design system and existing list/detail patterns.

**Out of Scope**

- Create, edit, delete and bulk delete actions (later phases of the epic).
- The "Ports" tab in the network details view itself (depends on #1019).
- Filters beyond search (status, device owner).

**Related Issues**

- Epic: #816
- Depends on: [Task: Ports BFF](https://github.com/cobaltcore-dev/aurora-dashboard/issues/1381)
- Related: #1019

**Additional Context**

- The device ID is shown below the device owner in the list, as in elektra; there is no name lookup for devices.

