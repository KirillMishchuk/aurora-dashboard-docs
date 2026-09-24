import { useState, useEffect } from "react"
import { Trans, useLingui } from "@lingui/react/macro"
import { trpcReact } from "@/client/trpcClient"
import { Modal, ModalFooter, ButtonRow, TextInput, Stack, Status, Button } from "@cloudoperators/juno-ui-components"
import type { Bucket } from "@/server/Storage/types/ceph"
import { useProjectId } from "@/client/hooks/useProjectId"
import { useModalTracking } from "@/client/hooks/useModalTracking"

interface DeleteBucketModalProps {
  isOpen: boolean
  bucket: Bucket | null
  onClose: () => void
  onSuccess?: (bucketName: string) => void
  onError?: (bucketName: string, errorMessage: string) => void
}

export const DeleteBucketModal = ({ isOpen, bucket, onClose, onSuccess, onError }: DeleteBucketModalProps) => {
  const { t } = useLingui()
  const projectId = useProjectId()
  const [confirmName, setConfirmName] = useState("")
  const [nameError, setNameError] = useState<string | null>(null)

  const { trackClose, markSubmitted, resetTracking } = useModalTracking({
    isOpen,
    actionPrefix: "storage.ceph.bucket.delete",
  })

  const utils = trpcReact.useUtils()

  // Fetch authoritative bucket state (current objects, old versions/delete markers) — a single
  // bounded server-side scan. This modal is a live pre-delete check, so staleTime: 0 forces a
  // fresh answer on every open rather than serving a cached one (same convention as
  // EmptyBucketModal).
  const {
    data: bucketState,
    isLoading: isLoadingBucketState,
    isFetching: isFetchingBucketState,
    error: bucketStateError,
  } = trpcReact.storage.ceph.containers.getState.useQuery(
    { project_id: projectId ?? "", bucketName: bucket?.name ?? "" },
    { enabled: isOpen && bucket !== null, staleTime: 0 }
  )

  const deleteBucketMutation = trpcReact.storage.ceph.containers.delete.useMutation({
    onSettled: () => {
      utils.storage.ceph.containers.list.invalidate()
    },
  })

  useEffect(() => {
    if (!isOpen) {
      setConfirmName("")
      setNameError(null)
      deleteBucketMutation.reset()
      resetTracking()
    }
  }, [isOpen, bucket?.name])

  const handleClose = () => {
    setConfirmName("")
    setNameError(null)
    deleteBucketMutation.reset()
    resetTracking()
    onClose()
  }

  const handleConfirmNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setConfirmName(value)
    if (nameError) setNameError(null)
  }

  const handleSubmit = () => {
    if (!bucket) return
    if (bucketStateError) return
    if (confirmName.trim() !== bucket.name) {
      setNameError(t`Bucket name does not match`)
      return
    }

    markSubmitted()

    // Capture bucket name before async operation to avoid dereferencing null bucket in callbacks
    const bucketName = bucket.name

    deleteBucketMutation.mutate(
      { project_id: projectId, bucketName },
      {
        onSuccess: () => {
          handleClose()
          onSuccess?.(bucketName)
        },
        // Deliberately still the close-then-toast shape, unlike `DeleteVersionsModal` and
        // `EmptyBucketModal`, which keep their modal open and report inline. Those two run
        // mutations that destroy data, so a lost report costs the user the only record of what
        // was removed. `containers.delete` destroys nothing: S3 refuses a non-empty bucket
        // outright, and this modal has already gated on `cannotDelete` before enabling the
        // button, so a failure here is "nothing happened, try again" rather than a partial
        // result that has to be read.
        onError: (error) => {
          handleClose()
          onError?.(bucketName, error.message)
        },
      }
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSubmit()
  }

  if (!isOpen || !bucket) return null

  // Bucket cannot be deleted if it has:
  // 1. Current objects (!isEmpty) - show "Empty the bucket"
  // 2. Old versions or any delete markers in a versioned bucket - show "Delete all versions"
  // 3. An unconfirmed scan (isPartialScan) - show "contents could not be fully verified". This
  //    must block deletion rather than fail open: unlike the UI gates that only hide an action
  //    (fail-open there is safe — the worst case is an extra click), enabling the delete button
  //    on unverified data risks deleting a bucket that actually still has content.
  const hasCurrentObjects = !(bucketState?.isEmpty ?? true)
  const hasVersionsInVersionedBucket = bucketState?.hasOldVersionsOrDeleteMarkers ?? false
  const isPartialScan = bucketState?.isPartialScan ?? false
  const cannotDelete = hasCurrentObjects || hasVersionsInVersionedBucket || isPartialScan
  const errorMessage = bucketStateError?.message
  // `isLoading` alone is `isPending && isFetching`, and `isPending` is false whenever the
  // cache already holds an entry — which it almost always does here, because the bucket
  // header's `useBucketInfo` keeps the very same `getState` query warm with a 30s staleTime.
  // Rendering the verdict off that entry defeats the point of `staleTime: 0`: this modal is
  // a live pre-delete check, so a refetch in flight means "not known yet", not "known".
  const isLoading = isLoadingBucketState || isFetchingBucketState

  return (
    <Modal
      title={t`Delete Bucket`}
      open={isOpen}
      onCancel={() => {
        trackClose()
        handleClose()
      }}
      confirmButtonLabel={cannotDelete ? undefined : t`Delete Bucket`}
      confirmButtonVariant={cannotDelete ? undefined : "primary-danger"}
      onConfirm={cannotDelete ? undefined : handleSubmit}
      cancelButtonLabel={cannotDelete ? undefined : t`Cancel`}
      modalFooter={
        cannotDelete ? (
          <ModalFooter className="flex justify-end">
            <ButtonRow>
              <Button variant="primary" onClick={handleClose} data-testid="delete-has-objects-close-button">
                <Trans>Close</Trans>
              </Button>
            </ButtonRow>
          </ModalFooter>
        ) : undefined
      }
      size="small"
      disableConfirmButton={
        deleteBucketMutation.isPending || isLoading || !!bucketStateError || confirmName.trim() !== bucket.name
      }
      // All three are needed to actually block dismissal during the delete: juno's Modal gates
      // Esc on `closeable && closeOnEsc` and never consults the two button props, so those two
      // alone leave the key live. `closeable={false}` would cover it as well, but it unmounts
      // the footer and the close icon instead of disabling them, taking the confirm button too.
      disableCancelButton={deleteBucketMutation.isPending}
      disableCloseButton={deleteBucketMutation.isPending}
      closeOnEsc={!deleteBucketMutation.isPending}
    >
      <Stack direction="vertical" gap="6">
        {bucketStateError && (
          <Status status="error" title={t`Failed to Check Bucket Contents`} body={errorMessage} className="mt-0" />
        )}

        {isLoading ? (
          <Status status="progress" title={t`Checking Bucket Contents...`} className="mt-0" />
        ) : cannotDelete ? (
          <div className="text-theme-default">
            <p className="mb-4">
              <Trans>This bucket cannot be deleted yet. Do the following to be able to delete the bucket:</Trans>
            </p>
            <ul className="list-disc space-y-1 pl-5">
              {hasCurrentObjects && (
                <li>
                  <Trans>Empty the bucket</Trans>
                </li>
              )}
              {hasVersionsInVersionedBucket && (
                <li>
                  <Trans>Delete all versions and delete markers</Trans>
                </li>
              )}
              {isPartialScan && (
                <li>
                  <Trans>Bucket contents could not be fully verified — refresh and try again</Trans>
                </li>
              )}
            </ul>
          </div>
        ) : (
          <>
            <p className="text-theme-default">
              <Trans>
                This action is irreversible. Deleting a bucket permanently removes it and cannot be undone. The bucket
                must be empty before deletion.
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
              disabled={deleteBucketMutation.isPending}
              placeholder={bucket.name}
            />
          </>
        )}
      </Stack>
    </Modal>
  )
}
