# #1381: [Task](networking): Ports BFF

State: OPEN · https://github.com/cobaltcore-dev/aurora-dashboard/issues/1381

**Task Description**

Part of #816

Provide the tRPC BFF layer for OpenStack Neutron ports, so the Aurora Dashboard can list, show and manage ports. Ports are first-class resources in the project scope: the same procedures must serve a project-wide ports view and a view scoped to a single network. All operations are project-scoped and use the current Keystone token.

API reference: https://docs.openstack.org/api-ref/network/v2/index.html#ports

**Sub-tasks**

- [ ] Zod schemas for port requests and responses (fixed IPs, security groups, allowed address pairs)
- [ ] Procedures: list (optionally filtered by network), get details, create, update, delete
- [ ] Additional data the UI needs that isn't part of the port object itself: network, subnet and security group names, IP version of each fixed IP
- [ ] User-friendly error messages for common Neutron errors (e.g. IP or MAC address already in use, port still in use by a router, quota exceeded, permission denied)
- [ ] Registration under the network tRPC router
- [ ] Unit tests for schemas, helpers and procedures
- [ ] BFF documentation

**Acceptance Criteria**

- [ ] All procedures above are available, and both input and Neutron responses are validated with Zod.
- [ ] Lists are restricted to the current project and can be narrowed to one network.
- [ ] List and details responses contain everything the list and details views need, including related resource names.
- [ ] Missing related names (e.g. lookups not permitted) don't break the list or details; IDs are returned instead.
- [ ] Neutron errors are mapped to tRPC errors with clear messages.
- [ ] Tests cover success and error cases.
- [ ] Documentation is added alongside the existing service docs.

**Out of Scope**

- UI pages and components (separate task).
- Port security toggle, tag editor and allowed address pairs management in the UI (Phase 4 of the epic).

**Related Issues**

- Epic: #816
- Related: #1019 (Networks, "Ports" tab in the network details view)

**Additional Context**

- Permission keys `network:ports:list`, `read`, `create`, `update` and `delete` already exist in the network policy mapping.
- Neutron reports quota errors as 409 Conflict.
- Ports owned by a service (e.g. router interfaces) can't be deleted via the port API.

