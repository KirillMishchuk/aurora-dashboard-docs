import { createRouter } from "@tanstack/react-router"
import { routeTree } from "./routeTree.gen"
import type { TrpcReact, TrpcClient } from "./trpcClient"
import type { ServiceExtension } from "./AuroraApp"
import { ServiceLevelDefaultError } from "./components/Errors/ServiceLevelDefaultError"

export function createAuroraRouter(
  trpcReact: TrpcReact,
  trpcClient: TrpcClient,
  serviceExtensions?: ServiceExtension[]
) {
  return createRouter({
    routeTree,
    // Fallback for a URL that matches no route at all — `/projects/<id>/nonsense` and the like.
    //
    // Which route answers such a URL is decided by `findGlobalNotFoundRouteId`, and with the
    // default `notFoundMode` ("fuzzy") that is the deepest *matched* route having children —
    // picked without looking at whether it declares a `notFoundComponent`. So this fallback is
    // reached whenever that layout route declares none: `$projectId`, for one. `$storageType`
    // used to be another, until it got its own storage-aware boundary.
    //
    // It does NOT cover a `notFound()` thrown from a loader, such as
    // `services/$serviceType`'s. That path goes through `getNotFoundBoundaryIndex`, which
    // walks *up* to the nearest route that does declare a `notFoundComponent` — and the root
    // always does (`__root.tsx` → `PageNotFound`), so the fallback never gets the chance.
    defaultNotFoundComponent: ServiceLevelDefaultError,
    context: {
      trpcReact,
      trpcClient,
      auth: undefined!,
      navItems: [],
      handleThemeToggle: undefined!,
      slots: undefined,
      onTrackEvent: undefined,
      serviceExtensions: serviceExtensions ?? [],
    },
  })
}

// Type registration — uses the shape of a router instance for global type inference
declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAuroraRouter>
  }
}
