import { useState } from "react"
import { Trans, useLingui } from "@lingui/react/macro"
import { trpcReact } from "@/client/trpcClient"
import {
  Modal,
  ModalFooter,
  Button,
  ButtonRow,
  TextInput,
  Stack,
  Checkbox,
  Status,
  Message,
} from "@cloudoperators/juno-ui-components"
import { Bucket } from "@/server/Storage/types/ceph"
import { useProjectId } from "@/client/hooks/useProjectId"
import { useModalTracking } from "@/client/hooks/useModalTracking"
import { invalidateBucketQueries } from "../hooks/invalidateBucketQueries"

interface EmptyBucketModalProps {
  isOpen: boolean
  bucket: Bucket | null
  onClose: () => void
  onSuccess?: (bucketName: string, deletedCount: number) => void
}

export const EmptyBucketModal = ({ isOpen, bucket, onClose, onSuccess }: EmptyBucketModalProps) => {
  const { t } = useLingui()
  const projectId = useProjectId()
  const [confirmName, setConfirmName] = useState("")
  const [nameError, setNameError] = useState<string | null>(null)
  const [deleteVersionsAndMarkers, setDeleteVersionsAndMarkers] = useState(false)
  const [mutationError, setMutationError] = useState<string | null>(null)

  const { trackClose, markSubmitted, resetTracking } = useModalTracking({
    isOpen,
    actionPrefix: "storage.ceph.bucket.empty",
  })

  const utils = trpcReact.useUtils()

  // Query authoritative bucket state (versioning status, current objects, old versions/delete
  // markers) — a single bounded server-side scan. Always runs (regardless of versioning status)
  // to get accurate live data for the truly-empty check below — bucket.count from the list
  // cache can be stale.
  //
  // This carries the versioning status too, so there is no separate `versioning.getStatus`
  // query beside it: `getState` issues `GetBucketVersioning` anyway, and with staleTime: 0 a
  // second one would be a guaranteed duplicate round-trip on every open of this modal.
  const {
    data: bucketState,
    isLoading: isLoadingBucketState,
    isFetching: isFetchingBucketState,
    error: bucketStateError,
  } = trpcReact.storage.ceph.containers.getState.useQuery(
    {
      project_id: projectId ?? "",
      bucketName: bucket?.name ?? "",
    },
    {
      enabled: !!projectId && !!bucket && isOpen,
      // App-wide default staleTime is 60s (see App.tsx) — override it so every
      // open of this modal re-verifies live instead of serving cached data.
      staleTime: 0,
    }
  )

  const versioningStatus = bucketState ? { status: bucketState.status } : undefined
  const isBucketEmpty = bucketState?.isEmpty ?? false
  const hasOnlyDeleteMarkers = bucketState?.hasOnlyDeleteMarkers ?? false
  const hasOldVersionsOrDeleteMarkers = bucketState?.hasOldVersionsOrDeleteMarkers ?? false
  // The scan hit its page ceiling (or hasn't resolved yet) and couldn't confirm every flag —
  // same guard as before (`isVersionDataComplete`), sourced from the server's honest
  // `isPartialScan` rather than inferred from `isTruncated` on a first-page-only probe. Fall
  // back to the standard destructive form instead of risking a wrong "safe" branch.
  const isVersionDataComplete = !(bucketState?.isPartialScan ?? true)
  const isBucketEmptyWithVersions = isVersionDataComplete && isBucketEmpty && hasOnlyDeleteMarkers
  // Bucket has zero current objects AND zero versions/delete markers of any kind —
  // genuinely nothing to empty (unlike isBucketEmptyWithVersions, which still has
  // delete markers to clean up). Distinct render branch below shows an info-only view.
  const isTrulyEmpty = isVersionDataComplete && isBucketEmpty && !hasOldVersionsOrDeleteMarkers

  const emptyBucketMutation = trpcReact.storage.ceph.objects.deleteAll.useMutation({
    // Invalidation runs on every outcome - a failed wipe can still have removed objects before
    // it stopped. Closing does not: a failure has to stay open to report itself inside the
    // modal (B.11), the same way `DeleteVersionsModal` does.
    onSettled: () => {
      invalidateBucketQueries(utils)
    },
  })

  const handleClose = () => {
    trackClose()
    setConfirmName("")
    setNameError(null)
    setDeleteVersionsAndMarkers(false)
    setMutationError(null)
    emptyBucketMutation.reset()
    resetTracking()
    onClose()
  }

  const handleConfirmNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setConfirmName(value)
    if (nameError) setNameError(null)
    if (mutationError) setMutationError(null)
  }

  const handleSubmit = () => {
    if (!bucket) return
    if (confirmName.trim() !== bucket.name) {
      setNameError(t`Bucket name does not match`)
      return
    }

    setMutationError(null)
    markSubmitted()

    // Capture bucket name before async operation to avoid dereferencing null bucket in callbacks
    const bucketName = bucket.name

    // If bucket is empty with only delete markers, always delete versions
    const shouldDeleteVersions = isBucketEmptyWithVersions || deleteVersionsAndMarkers

    emptyBucketMutation.mutate(
      {
        project_id: projectId,
        containerName: bucketName,
        includeVersionsAndDeleteMarkers: shouldDeleteVersions,
      },
      {
        onSuccess: (deletedCount) => {
          onSuccess?.(bucketName, deletedCount)
          handleClose()
        },
        onError: (error) => {
          setMutationError(error.message)
        },
      }
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSubmit()
  }

  if (!isOpen || !bucket) return null

  const bucketName = bucket.name
  // `isLoading` alone is `isPending && isFetching`, and `isPending` is false whenever the
  // cache already holds an entry — which it almost always does here (the bucket header's
  // `useBucketInfo` keeps this same `getState` query warm). There is no S3-side backstop for
  // this modal — `isBucketEmptyWithVersions` forces `includeVersionsAndDeleteMarkers: true`
  // with no checkbox (see `shouldDeleteVersions` above) — so a refetch in flight has to be
  // treated as "not known yet", not "known".
  // An in-flight refetch means "not known yet" while the modal is still deciding what to offer.
  // It must not mean that once a run has already failed: this mutation's own `onSettled`
  // invalidates `containers.getState`, this component is an active observer of it, so the
  // refetch fires immediately after `setMutationError` and would otherwise swap the report the
  // user is reading for a spinner - and, once it resolved, possibly for a different branch.
  const isLoading = isLoadingBucketState || (isFetchingBucketState && !mutationError)
  const hasQueryError = !!bucketStateError

  // If bucket is empty with only delete markers, show "Delete Versions" UI
  if (isBucketEmptyWithVersions && !isLoading) {
    return (
      <Modal
        title={t`Delete Versions`}
        open={isOpen}
        onCancel={handleClose}
        confirmButtonLabel={t`Delete Versions`}
        confirmButtonVariant="primary-danger"
        onConfirm={handleSubmit}
        cancelButtonLabel={t`Cancel`}
        size="small"
        disableConfirmButton={emptyBucketMutation.isPending || confirmName.trim() !== bucket.name || hasQueryError}
        // All three are needed to actually block dismissal during the wipe: juno's Modal gates Esc
        // on `closeable && closeOnEsc` and never consults the two button props.
        disableCancelButton={emptyBucketMutation.isPending}
        disableCloseButton={emptyBucketMutation.isPending}
        closeOnEsc={!emptyBucketMutation.isPending}
      >
        <Stack direction="vertical" gap="6">
          {hasQueryError && (
            <Message variant="error" role="alert" aria-live="assertive" data-testid="empty-bucket-state-error">
              <Trans>Unable to verify bucket versioning status and contents. Try again.</Trans>
            </Message>
          )}

          {mutationError && (
            <EmptyBucketErrorMessage
              title={isBucketEmptyWithVersions ? t`Failed to Delete Versions` : t`Failed to Empty Bucket`}
              bucketName={bucketName}
              errorMessage={mutationError}
            />
          )}

          <p className="text-theme-default m-0">
            <Trans>
              This action will permanently delete all versions and delete markers. This will enable you to delete the
              bucket. This action cannot be undone.
            </Trans>
          </p>

          <TextInput
            label={t`Type the bucket name to confirm`}
            required
            value={confirmName}
            onChange={handleConfirmNameChange}
            onKeyDown={handleKeyDown}
            invalid={!!nameError}
            errortext={nameError || undefined}
            disabled={emptyBucketMutation.isPending || hasQueryError}
            placeholder={bucket.name}
            autoFocus
          />
        </Stack>
      </Modal>
    )
  }

  // Bucket is genuinely empty — nothing to delete, show an info-only view
  if (isTrulyEmpty && !isLoading) {
    return (
      <Modal
        title={t`Empty Bucket`}
        open={isOpen}
        onCancel={handleClose}
        size="small"
        modalFooter={
          <ModalFooter className="flex justify-end">
            <ButtonRow>
              <Button variant="primary" onClick={handleClose} data-testid="empty-info-close-button">
                <Trans>Close</Trans>
              </Button>
            </ButtonRow>
          </ModalFooter>
        }
      >
        <Stack direction="vertical" gap="6">
          {/* Reachable after a failed run: a wipe that errored partway can still have removed
              every object, flipping the bucket into this branch. Without the report here, the
              only record of the failure would vanish behind "already empty". */}
          {mutationError && (
            <EmptyBucketErrorMessage
              title={t`Failed to Empty Bucket`}
              bucketName={bucketName}
              errorMessage={mutationError}
            />
          )}

          {hasQueryError ? (
            <Message variant="error" role="alert" aria-live="assertive" data-testid="empty-bucket-state-error">
              {/* One query now answers both, so there is no longer a partial-failure case to
                  distinguish — versioning status and contents fail or succeed together. */}
              <Trans>Unable to verify bucket versioning status and contents. Try again.</Trans>
            </Message>
          ) : (
            <p className="text-theme-default py-2">
              <Trans>This bucket is already empty.</Trans>
            </p>
          )}
        </Stack>
      </Modal>
    )
  }

  // Otherwise show normal "Empty Bucket" UI
  return (
    <Modal
      title={t`Empty Bucket`}
      open={isOpen}
      onCancel={handleClose}
      confirmButtonLabel={t`Empty Bucket`}
      confirmButtonVariant="primary-danger"
      onConfirm={handleSubmit}
      cancelButtonLabel={t`Cancel`}
      size="small"
      disableConfirmButton={
        emptyBucketMutation.isPending || isLoading || confirmName.trim() !== bucket.name || hasQueryError
      }
      // All three are needed to actually block dismissal during the wipe: juno's Modal gates Esc
      // on `closeable && closeOnEsc` and never consults the two button props.
      disableCancelButton={emptyBucketMutation.isPending}
      disableCloseButton={emptyBucketMutation.isPending}
      closeOnEsc={!emptyBucketMutation.isPending}
    >
      {isLoading ? (
        <Status status="progress" title={t`Checking Bucket Contents...`} className="mt-0" />
      ) : (
        <Stack direction="vertical" gap="6">
          {hasQueryError && (
            <Message variant="error" role="alert" aria-live="assertive" data-testid="empty-bucket-state-error">
              <Trans>Unable to verify bucket versioning status and contents. Try again.</Trans>
            </Message>
          )}

          {mutationError && (
            <EmptyBucketErrorMessage
              title={isBucketEmptyWithVersions ? t`Failed to Delete Versions` : t`Failed to Empty Bucket`}
              bucketName={bucketName}
              errorMessage={mutationError}
            />
          )}

          <p className="text-theme-default m-0">
            {versioningStatus && versioningStatus.status !== "Unversioned" ? (
              <Trans>
                This action will permanently delete all objects from {bucketName}. You may choose to also delete all
                versions and delete markers. This will enable you to delete the bucket. This action cannot be undone.
              </Trans>
            ) : (
              <Trans>
                This action will permanently delete all objects from {bucketName}. This action cannot be undone.
              </Trans>
            )}
          </p>

          {versioningStatus && versioningStatus.status !== "Unversioned" && (
            <Checkbox
              checked={deleteVersionsAndMarkers}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDeleteVersionsAndMarkers(e.target.checked)}
              label={t`Also delete all versions and all delete markers`}
              disabled={emptyBucketMutation.isPending || hasQueryError}
            />
          )}

          <TextInput
            label={t`Type the bucket name to confirm`}
            required
            value={confirmName}
            onChange={handleConfirmNameChange}
            onKeyDown={handleKeyDown}
            invalid={!!nameError}
            errortext={nameError || undefined}
            disabled={emptyBucketMutation.isPending || hasQueryError}
            placeholder={bucket.name}
            autoFocus
          />
        </Stack>
      )}
    </Modal>
  )
}

// Same msgid the removed toast (`getBucketEmptyErrorToast`) used to render, so the catalogue is
// unchanged. Destructured to plain variables first - lingui's message linter flags property
// access inside `{}` interpolation.
const EmptyBucketErrorMessage = ({
  title,
  bucketName,
  errorMessage,
}: {
  title: string
  bucketName: string
  errorMessage: string
}) => (
  <Message variant="error" title={title} role="alert" aria-live="assertive" data-testid="empty-bucket-error">
    <EmptyBucketErrorBody bucketName={bucketName} errorMessage={errorMessage} />
  </Message>
)

const EmptyBucketErrorBody = ({ bucketName, errorMessage }: { bucketName: string; errorMessage: string }) => (
  <Trans>
    Could not empty bucket "{bucketName}": {errorMessage}
  </Trans>
)
