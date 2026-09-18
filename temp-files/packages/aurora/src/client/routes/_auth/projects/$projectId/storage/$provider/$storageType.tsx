import { createFileRoute, Outlet, useNavigate, useParams } from "@tanstack/react-router"
import { Button } from "@cloudoperators/juno-ui-components"
import { useLingui } from "@lingui/react/macro"
import type { RouteInfo } from "@/client/routes/routeInfo"
import { useSetBreadcrumb } from "@/client/hooks/useSetBreadcrumb"
import { RouteIdLevelDefaultError } from "@/client/components/Errors/RouteIdLevelDefaultError"
import { STORAGE_PROVIDER, isStorageProvider, storageTypeFor } from "@/client/utils/storageProviders"

/**
 * Catches any address under `/storage/$provider/$storageType/` that matches no route —
 * `.../demo-bucket-1/object` (mistyped tail) or `.../demo-bucket-1` (truncated link).
 *
 * Without it these fall through to the router's global `defaultNotFoundComponent`, which
 * knows nothing about storage and offers only the project overview — a long way back from
 * a URL that is one segment away from correct.
 *
 * The exit is the provider's list. A button straight to the container the URL names was
 * tried and dropped: the name is unmatched path here rather than a validated route param
 * (there is no `$containerName` route, only the `$containerName/objects` leaf), so it would
 * have been a guess that could land on a second 404 — and the list is one click from the
 * container anyway.
 */
function StorageTypeNotFound() {
  const { t } = useLingui()
  const navigate = useNavigate()
  // `strict: false` for the same reason as in the other storage 404s: this renders in a
  // match that is in its notFound state.
  const { projectId, provider } = useParams({ strict: false })

  // Nothing in the URL reaching this boundary has been validated — the layout route has no
  // guard, so `/storage/garbage/garbage/x` renders here just as readily as a mistyped tail
  // under a real provider. So the exit is offered only for a provider we recognise, and its
  // noun is derived rather than echoed back: `/storage/ceph/containers/my-bucket/oops` also
  // lands here, and `containers` is exactly what the list route would 404 on. Answering one
  // 404 with the next is the thing this boundary exists to avoid.
  const listProvider = isStorageProvider(provider) ? provider : undefined

  return (
    <RouteIdLevelDefaultError
      errorTitle={t`Page Not Found`}
      errorDescription={t`This address is not valid for this object storage service.`}
      action={
        projectId && listProvider ? (
          <Button
            variant="primary"
            onClick={() =>
              navigate({
                to: "/projects/$projectId/storage/$provider/$storageType",
                params: { projectId, provider: listProvider, storageType: storageTypeFor(listProvider) },
              })
            }
          >
            {listProvider === STORAGE_PROVIDER.CEPH ? t`Back to Buckets` : t`Back to Containers`}
          </Button>
        ) : undefined
      }
    />
  )
}

export const Route = createFileRoute("/_auth/projects/$projectId/storage/$provider/$storageType")({
  staticData: {
    section: "storage",
    service: "containers",
  } satisfies RouteInfo,
  component: StorageTypeLayout,
  notFoundComponent: StorageTypeNotFound,
})

function StorageTypeLayout() {
  const { t } = useLingui()
  const { provider } = Route.useParams()
  // Behavior unchanged: an unknown provider still yields the neutral "Storage" crumb
  // above the 404. Only the mapping now goes through the shared narrowing helper, so
  // no sixth hardcoded swift/ceph pairing survives.
  const label = isStorageProvider(provider)
    ? provider === STORAGE_PROVIDER.SWIFT
      ? t`Object Storage (Swift)`
      : t`Object Storage (Ceph)`
    : t`Storage`
  useSetBreadcrumb(Route.id, label)
  return <Outlet />
}
