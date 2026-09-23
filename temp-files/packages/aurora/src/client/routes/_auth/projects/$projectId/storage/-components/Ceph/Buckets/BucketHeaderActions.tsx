import { useLingui } from "@lingui/react/macro"
import { Button, PopupMenu, PopupMenuItem, PopupMenuOptions, PopupMenuToggle } from "@cloudoperators/juno-ui-components"
import type { ModalType } from "./BucketModals"

interface BucketHeaderActionsProps {
  versioningStatus?: {
    status: "Enabled" | "Suspended" | "Unversioned"
  }
  hasPolicy: boolean
  hasOldVersionsOrDeleteMarkers: boolean
  onOpenModal: (modal: ModalType) => void
  canUpdateVersioning: boolean
  canUpdatePolicy: boolean
  canDeletePolicy: boolean
  canEmptyBucket: boolean
  canDeleteBucket: boolean
  canDeleteVersions: boolean
}

/**
 * Bucket header actions component
 *
 * Displays:
 * - Policy button (primary or subdued based on whether policy exists)
 * - Actions dropdown with versioning, policy, and bucket management options
 *
 * Every item in this menu is a gated mutation with no always-visible read action, so the
 * whole menu is hidden (not just its items) when nothing is available otherwise it would
 * render as an empty popup for a read-only user.
 */
export const BucketHeaderActions = ({
  versioningStatus,
  hasPolicy,
  hasOldVersionsOrDeleteMarkers,
  onOpenModal,
  canUpdateVersioning,
  canUpdatePolicy,
  canDeletePolicy,
  canEmptyBucket,
  canDeleteBucket,
  canDeleteVersions,
}: BucketHeaderActionsProps) => {
  const { t } = useLingui()

  const versioningState = canUpdateVersioning ? versioningStatus?.status : undefined
  const canEnableVersioning = versioningState === "Unversioned" || versioningState === "Suspended"
  const canSuspendVersioning = versioningState === "Enabled"
  const canToggleVersioning = canEnableVersioning || canSuspendVersioning
  const canShowDeletePolicy = hasPolicy && canDeletePolicy
  // "Empty Bucket" is permission-gated only — row-level gating on cached bucket state is what
  // makes the action disappear from a non-empty bucket whose state couldn't be fully checked.
  // EmptyBucketModal already has a live "already empty" branch for the case where it truly is.
  const canShowEmptyBucket = canEmptyBucket
  // Fail-closed: this opens a modal that permanently and unrestorably deletes every non-current
  // version, so an unconfirmed scan must not be the thing that advertises it — `false` here can
  // mean "none found" or "could not check", and only the first justifies offering the action.
  // This is no dead end: "Empty Bucket" is always available when there is genuinely something to
  // clean up.
  const canShowDeleteVersions = hasOldVersionsOrDeleteMarkers && canDeleteVersions

  const hasAnyAction =
    canToggleVersioning ||
    canUpdatePolicy ||
    canShowDeletePolicy ||
    canShowEmptyBucket ||
    canShowDeleteVersions ||
    canDeleteBucket

  if (!hasAnyAction) {
    return null
  }

  return (
    <PopupMenu>
      <PopupMenuToggle as="div">
        <Button icon="moreVert" title={t`Bucket actions`} aria-label={t`Bucket actions`} />
      </PopupMenuToggle>
      <PopupMenuOptions>
        {canEnableVersioning && (
          <PopupMenuItem label={t`Enable Versioning`} onClick={() => onOpenModal("enableVersioning")} />
        )}
        {canSuspendVersioning && (
          <PopupMenuItem label={t`Suspend Versioning`} onClick={() => onOpenModal("suspendVersioning")} />
        )}
        {canUpdatePolicy && (
          <PopupMenuItem label={hasPolicy ? t`Edit Policy` : t`Add Policy`} onClick={() => onOpenModal("policy")} />
        )}
        {canShowDeletePolicy && <PopupMenuItem label={t`Delete Policy`} onClick={() => onOpenModal("deletePolicy")} />}
        {canShowEmptyBucket && <PopupMenuItem label={t`Empty Bucket`} onClick={() => onOpenModal("emptyBucket")} />}
        {canShowDeleteVersions && (
          <PopupMenuItem label={t`Delete Versions`} onClick={() => onOpenModal("deleteVersions")} />
        )}
        {canDeleteBucket && <PopupMenuItem label={t`Delete Bucket`} onClick={() => onOpenModal("deleteBucket")} />}
      </PopupMenuOptions>
    </PopupMenu>
  )
}
