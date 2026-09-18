import { createFileRoute, useParams, type NotFoundRouteComponent } from "@tanstack/react-router"
import { z } from "zod"
import { ErrorBoundary } from "react-error-boundary"
import { SwiftContainers } from "../../-components/Swift/Containers"
import { CephBuckets } from "../../-components/Ceph/Buckets"
import { Trans, useLingui } from "@lingui/react/macro"
import type { RouteInfo } from "@/client/routes/routeInfo"
import { ContentHeader } from "@/client/components/ContentHeader/ContentHeader"
import { guardStorageRoute } from "../../-components/utils/serviceAvailability"
import { StorageNotFound } from "../../-components/StorageNotFound"
import { STORAGE_PROVIDER, isStorageProvider } from "@/client/utils/storageProviders"

// Search params schema
// - sortBy: active sort column — persisted for deep links and back navigation
// - sortDirection: "asc" | "desc" — persisted alongside sortBy
// - search: active filter string — persisted so deep links preserve the current search
const containersSearchSchema = z.object({
  sortBy: z.enum(["name", "count", "bytes", "last_modified"]).optional(),
  sortDirection: z.enum(["asc", "desc"]).optional(),
  search: z.string().optional(),
})

export const Route = createFileRoute("/_auth/projects/$projectId/storage/$provider/$storageType/")({
  staticData: {
    section: "storage",
    service: "containers",
    analytics: {
      name: "storage.objectstore.list",
    },
  } satisfies RouteInfo,
  validateSearch: containersSearchSchema,
  // `head` runs for the notFound boundary too (it's rendered in this route's own match
  // position), so the fallback must not name a page that does not exist (D13) — hence
  // the neutral "Object Storage" instead of the old "Storage Overview".
  head: ({ match }) => ({
    meta: [
      {
        title: isStorageProvider(match.params.provider)
          ? match.params.provider === STORAGE_PROVIDER.SWIFT
            ? "Object Storage (Swift)"
            : "Object Storage (Ceph)"
          : "Object Storage",
      },
    ],
  }),
  component: () => {
    return <StorageDashboard />
  },
  // The router spreads the whole notFound error object into this component's props, so
  // `notFound({ data: { reason } })` reaches it as a `data` prop (see StorageNotFound for
  // the three files that establish this). `NotFoundRouteProps` does model that prop, but
  // only as `data?: unknown` (router-core route.d.ts) — and StorageNotFound narrows it to
  // the reason union, which makes it unassignable to a component typed for `unknown`.
  // Hence the cast.
  //
  // What the cast costs: nothing checks that the narrowed shape matches what the loader
  // actually throws, so renaming a reason compiles clean and silently falls back to the
  // generic copy. StorageNotFound.test.tsx guards that pairing by throwing a real
  // `notFound()` rather than handing the component props directly.
  notFoundComponent: StorageNotFound as NotFoundRouteComponent,
  // The guard runs here rather than in `beforeLoad`, and there is no second hook:
  //   - `notFound()` is only intercepted by notFoundComponent when thrown from a loader
  //     (see services/$serviceType.tsx for the same constraint), so it cannot move up;
  //   - a `redirect` thrown from the same loader still wins, because guardStorageRoute
  //     runs that check first and it short-circuits.
  // Verified against the installed router (v1.168.22) on a real route tree, including the
  // case where both checks would fire. One hook also means one `getAvailableServices`
  // call, with no need to pass the result through beforeLoad's context — which this
  // router version doesn't surface in `loader`'s inferred context type anyway.
  loader: async ({ context, params }) => {
    const { trpcClient } = context
    // A missing client is a wiring bug, not an answer about the project. Without this it
    // would flow into the guard as an empty catalog and come back out as "this project
    // has no object storage" — a redirect to the overview that hides the real cause.
    if (!trpcClient) {
      throw new Error("trpcClient is not available in route context")
    }
    const availableServices = (await trpcClient.auth.getAvailableServices.query()) ?? []
    guardStorageRoute(availableServices, params)
  },
})

function StorageDashboard() {
  const { project, provider } = useParams({
    from: "/_auth/projects/$projectId/storage/$provider/$storageType/",
    select: (params) => {
      return { project: params.projectId, provider: params.provider, storageType: params.storageType }
    },
  })

  const { t } = useLingui()

  let pageTitle: string
  switch (provider) {
    case STORAGE_PROVIDER.SWIFT:
      pageTitle = t`Object Storage (Swift)`
      break
    case STORAGE_PROVIDER.CEPH:
      pageTitle = t`Object Storage (Ceph)`
      break
    default:
      pageTitle = t`Storage Overview`
  }

  return (
    <div>
      <ContentHeader title={pageTitle} projectId={project} />
      {project ? (
        <ErrorBoundary
          resetKeys={[project, provider]}
          fallback={
            <div className="p-4 text-center">
              <Trans>Error loading component</Trans>
            </div>
          }
        >
          {(() => {
            switch (provider) {
              case STORAGE_PROVIDER.SWIFT:
                return <SwiftContainers />
              case STORAGE_PROVIDER.CEPH:
                return <CephBuckets />
              default:
                return <div>Storage Overview Page</div> // replace when available
            }
          })()}
        </ErrorBoundary>
      ) : (
        <div className="p-4 text-center">
          <Trans>No project selected</Trans>
        </div>
      )}
    </div>
  )
}
