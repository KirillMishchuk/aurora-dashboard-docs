# #1019: [EPIC](networking):  Networks Management (DRAFT)

State: OPEN · https://github.com/cobaltcore-dev/aurora-dashboard/issues/1019

# Epic: OpenStack Networking Networks Management

## Description
Implement comprehensive OpenStack Networking (Neutron) Networks management within the Aurora Dashboard. This implementation enables users to view, create, update, and delete virtual networks (Layer 2 segments). It acts as the foundational networking feature, providing visibility into network topologies, associated subnets, MTU settings, and administrative states.

All operations are project-scoped, utilize existing OpenStack Keystone tokens, and strictly respect network access controls defined by the Aurora/OpenStack policy engine.

---

## Objectives
- Provide a complete tRPC-based BFF for Neutron Network operations.
- Enable users to manage the full lifecycle of virtual networks (CRUD).
- Provide clear visibility into associated Subnets and Ports from the Network detail view.
- Support advanced network configurations (Admin State, MTU visibility, Shared/External flags, Tags).
- Establish the foundational UI views upon which Subnets and Ports will be built.
- Enforce strict RBAC using Aurora's policy engine (`network:network:*` permissions).

---

## Acceptance Criteria
- [ ] tRPC BFF is implemented with complete Zod schema validation for Networks.
- [ ] Users can list, view, create, update, and delete networks (P1 & P2).
- [ ] Network Detail view clearly lists associated Subnets (read-only reference or linked).
- [ ] Advanced properties like MTU, Admin State, and Shared status are visible and manageable where appropriate (P3).
- [ ] Permission system correctly hides/disables actions for unauthorized users (e.g., creating shared/external networks usually requires admin rights).
- [ ] Comprehensive error handling provides user-friendly feedback for Neutron errors (e.g., preventing deletion of networks with active ports).
- [ ] All UI components follow the Aurora design system.
- [ ] Complete testing coverage (unit, integration, E2E) is achieved.

---

## Openstack API

https://docs.openstack.org/api-ref/network/v2/index.html#networks

## Technical Architecture & Request Flow

### System Architecture
```text
┌──────────┐       ┌──────────────────────────────┐       ┌──────────────┐
│          │ tRPC  │            BFF               │       │              │
│  UI      │◄─────►│  ┌─────────────────────────┐ │       │   Neutron    │
│          │       │  │      Service Layer      │◄├──────►│  (Network)   │
└──────────┘       │  └─────────────────────────┘ │       │              │
                   └──────────────────────────────┘       └──────────────┘
```

### Request Flow Example (Create Network)
```text
UI                          BFF                         Neutron
│                            │                             │
│── networks.create() ──────►│                             │
│                            │── POST /v2.0/networks ─────►│
│                            │◄── network details ─────────│
│◄── success ────────────────│                             │
```

---

## API Integration Mapping

| Feature | API Endpoint | Service | Priority |
|---------|--------------|---------|----------|
| List networks | `GET /v2.0/networks` | Neutron | P1 |
| Show network details | `GET /v2.0/networks/{id}` | Neutron | P1 |
| Create network | `POST /v2.0/networks` | Neutron | P2 |
| Delete network | `DELETE /v2.0/networks/{id}` | Neutron | P2 |
| Update network | `PUT /v2.0/networks/{id}` | Neutron | P2 |
| Network tags | `PUT /v2.0/networks/{id}/tags` | Neutron | P3 |

---

## Subtasks (Implementation Plan)

*Tasks will be converted to GitHub issues during sprint planning.*

### Phase 1: Foundation & Read Operations (P1)
- [ ] **(BFF)** Create/Extend Neutron client wrapper in `openstack-signal` for networks.
- [ ] **(BFF)** Define Zod schemas (`Network`, `NetworkListResponse`).
- [ ] **(BFF)** Implement `networks.list` and `networks.get` procedures.
- [ ] **(UI)** Create Networks List View with DataGrid, pagination, and filters (Name, Status, Shared).
- [ ] **(UI)** Create Network Detail Page showing basic info (Status, MTU, Admin State).
- [ ] **(UI)** Implement copy-to-clipboard for Network IDs.

### Phase 2: Write Operations (P2)
- [ ] **(BFF)** Implement `networks.create`, `networks.update`, and `networks.delete` procedures.
- [ ] **(UI)** Build "Create Network" modal (Name, Admin State toggle).
- [ ] **(UI)** Build "Edit Network" modal (Name, Admin State).
- [ ] **(UI)** Implement "Delete Network" flow with pre-checks (warn/block if subnets or ports exist).

### Phase 3: Advanced Features & Cross-Linking (P3)
- [ ] **(UI)** Integrate "Subnets" list/tab into the Network Detail Page.
- [ ] **(UI)** Integrate "Ports" list/tab into the Network Detail Page (linking to Ports Epic).
- [ ] **(BFF & UI)** Add Tag management editor to Network Detail view.
- [ ] **(UI)** Implement bulk deletion UI (multi-select in DataGrid).

### Phase 4: Polish & Permissions
- [ ] **(BFF)** Implement strict policy engine checks (`network:network:list`, `create`, `update`, `delete`).
- [ ] **(UI)** Ensure UI gracefully hides/disables actions based on user permissions (especially for `shared` or `router:external` flags).
- [ ] **(QA)** Write component tests for list, detail, and forms.
- [ ] **(QA)** Write E2E tests for the full flow: Create Network -> Update Network -> Delete Network.

---

## Milestones & Phasing
**Target:** 2026 Q2 - Production Readiness
- **Phase 1 (Q1):** Foundation + Read Operations (P1)
- **Phase 2 (Q1/Q2):** Write Operations (P2)
- **Phase 3 (Q2):** Advanced Features & Cross-Linking (P3)
- **Phase 4 (Q2):** Integration + Testing

---

## Business Value & Use Cases
- **Workload Isolation:** Create dedicated L2 segments for different application tiers (e.g., Web, DB).
- **Topology Management:** Provide the foundational layer required before creating subnets, routers, and launching instances.
- **Troubleshooting:** Quickly identify network states (ACTIVE/DOWN) and verify MTU sizes for performance tuning.
- **Organization:** Use tags to categorize networks by environment, team, or cost center.

---

## Reference Implementation / Code Drafts

*The following snippets serve as a technical blueprint for the BFF implementation.*

### 1. Context (`context.ts`)
```typescript
import { inferAsyncReturnType } from '@trpc/server';

export async function createContext({ req }) {
  return {
    userId: req.headers['x-user-id'] as string,
    projectId: req.headers['x-project-id'] as string,
    token: req.headers['x-auth-token'] as string,
    neutronUrl: process.env.NEUTRON_URL,
  };
}
export type Context = inferAsyncReturnType<typeof createContext>;
```

### 2. Network Types (`routers/networks/types.ts`)
```typescript
export interface Network {
  id: string;
  name: string;
  tenant_id: string;
  admin_state_up: boolean;
  status: 'ACTIVE' | 'DOWN' | 'BUILD' | 'ERROR';
  shared: boolean;
  mtu: number;
  subnets: string[]; // Array of Subnet IDs
  'router:external': boolean;
  port_security_enabled: boolean;
  created_at: string;
  updated_at: string;
  tags?: string[];
}
```

### 3. Networks Router (`routers/networks/router.ts`)
```typescript
import { router, protectedProcedure } from '../../trpc/trpc';
import { z } from 'zod';
import { NetworkService } from './service';

export const networksRouter = router({
  list: protectedProcedure
    .input(z.object({
      name: z.string().optional(),
      status: z.enum(['ACTIVE', 'DOWN', 'BUILD', 'ERROR']).optional(),
      shared: z.boolean().optional(),
    }))
    .query(async ({ ctx, input }) => {
      const service = new NetworkService(ctx);
      return service.listNetworks(input);
    }),

  create: protectedProcedure
    .input(z.object({
      name: z.string(),
      adminStateUp: z.boolean().default(true),
      portSecurityEnabled: z.boolean().optional(),
    }))
    .mutation(async ({ ctx, input }) => {
      const service = new NetworkService(ctx);
      return service.createNetwork(input);
    }),

  update: protectedProcedure
    .input(z.object({
      id: z.string(),
      name: z.string().optional(),
      adminStateUp: z.boolean().optional(),
    }))
    .mutation(async ({ ctx, input }) => {
      const service = new NetworkService(ctx);
      return service.updateNetwork(input.id, input);
    }),

  delete: protectedProcedure
    .input(z.object({
      id: z.string(),
    }))
    .mutation(async ({ ctx, input }) => {
      const service = new NetworkService(ctx);
      return service.deleteNetwork(input.id);
    }),
});
```
