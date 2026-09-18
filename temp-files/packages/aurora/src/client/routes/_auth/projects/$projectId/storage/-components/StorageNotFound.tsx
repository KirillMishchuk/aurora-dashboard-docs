import { Status, Button } from "@cloudoperators/juno-ui-components"
import { useLingui, Trans } from "@lingui/react/macro"
import { useNavigate, useParams } from "@tanstack/react-router"
import type { StorageNotFoundReason } from "./utils/serviceAvailability"

interface StorageNotFoundProps {
  data?: { reason?: StorageNotFoundReason }
}

// The router spreads the WHOLE notFound error object into this component's props, not its
// `data` field: `notFound(options)` just tags `options` with `isNotFound` and returns it
// (router-core/not-found.js), `Match.js:158` hands that object to `renderRouteNotFound`,
// and `renderRouteNotFound.js` renders `<notFoundComponent {...data} />` where `data` is
// the error. So `notFound({ data: { reason } })` arrives here as a `data` prop — reading a
// flat `reason` silently yields undefined and collapses every case into one message.
//
// Rendered as a route-level `notFoundComponent`, so it sits inside `AuroraLayout` and the
// breadcrumbs rather than the shell-less root `PageNotFound` (D7). No `Container` wrapper
// for that reason — it is already inside a layout.
export function StorageNotFound({ data }: StorageNotFoundProps) {
  const { t } = useLingui()
  const navigate = useNavigate()
  const { projectId } = useParams({ strict: false })

  const isBadUrl = data?.reason === "storage-type-mismatch"

  return (
    <Status
      status="error"
      code={404}
      title={isBadUrl ? t`Page Not Found` : t`Object Storage Not Found`}
      body={
        isBadUrl
          ? t`This address is not valid for this object storage service.`
          : t`This object storage service does not exist or is not available for this project.`
      }
      action={
        projectId ? (
          <Button variant="primary" onClick={() => navigate({ to: "/projects/$projectId", params: { projectId } })}>
            <Trans>Go to Project</Trans>
          </Button>
        ) : (
          // Unreachable from the storage routes (projectId is part of their path); kept so
          // the component never renders an actionless 404 if it is ever mounted elsewhere.
          <Button variant="primary" onClick={() => navigate({ to: "/projects" })}>
            <Trans>Go to Projects</Trans>
          </Button>
        )
      }
    />
  )
}
