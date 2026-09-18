import { notFound } from "@tanstack/react-router"
import { isTRPCClientError } from "@trpc/client"
import type { TrpcClient } from "@/client/trpcClient"
import type { ContainerInfo } from "@/server/Storage/types/swift"
import { STORAGE_PROVIDER, type StorageProvider } from "@/client/utils/storageProviders"

/**
 * What the probe learned, returned as loader data so the page can reuse it.
 *
 * Swift's probe is a HEAD that comes back with the container's object count and size —
 * the very summary `ContainerHeader` needs — so handing it on turns what would be a
 * duplicated request into a seeded cache entry. Ceph's probe is a bodiless HeadBucket,
 * so there is nothing to hand on and `containerInfo` stays undefined.
 */
export interface ContainerProbe {
  containerInfo?: ContainerInfo
  /**
   * When the answer arrived. Consumers seeding a query cache pass this as
   * `initialDataUpdatedAt`: the router may replay loader data it cached earlier, and
   * without the timestamp React Query would treat a stale answer as freshly fetched.
   */
  fetchedAt: number
}

/**
 * Reason carried by the `notFound()` this module throws.
 *
 * Deliberately NOT part of `StorageNotFoundReason`: those three reasons say the *address*
 * is wrong (bad provider, bad storage-type noun) and are answered by reading the URL;
 * this one says the address is well-formed but the *resource* behind it isn't there, and
 * only the API can answer it. The objects route renders them with different components.
 */
export const CONTAINER_NOT_FOUND = "container-not-found"

/** True only for a tRPC error whose server-side code was NOT_FOUND. */
const isNotFoundResponse = (error: unknown): boolean => isTRPCClientError(error) && error.data?.code === "NOT_FOUND"

/**
 * "Does this container/bucket exist?" — one request, before anything renders.
 *
 * Without it the page mounts for a container that isn't there and every child hook
 * discovers the same 404 on its own: for Ceph that is eight requests (bucket list,
 * versioning, policy, CORS, lifecycle, two object listings, permissions) ending in an
 * error banner under a header that still offers Delete and Empty for a bucket that
 * doesn't exist.
 *
 * Only a NOT_FOUND answer produces the 404. Anything else — `NO_CEPH_CREDENTIALS`
 * (FORBIDDEN, the case `CredentialPrompt` exists for), a permission denial, a 500, a dead
 * network — is deliberately swallowed so the page still renders and reports the real
 * problem itself. Turning those into "container not found" would be a lie, and the
 * credentials one would be a dead end: a 404 offers no way to add credentials.
 *
 * 404 and 403 stay distinct here because the route has to act differently on them, but
 * the page the 404 renders says "does not exist or is not accessible" — so the copy the
 * user sees still doesn't confirm whether someone else's container exists.
 *
 * Call from a `loader`: `notFound()` is only intercepted by `notFoundComponent` when
 * thrown from one (same constraint as `guardStorageRoute`).
 */
export const requireContainerExists = async (
  trpcClient: TrpcClient,
  params: { projectId: string; provider: StorageProvider; containerName: string }
): Promise<ContainerProbe> => {
  const { projectId, provider, containerName } = params

  let missing = false
  let containerInfo: ContainerInfo | undefined
  try {
    if (provider === STORAGE_PROVIDER.SWIFT) {
      // One HEAD — and it is the same request ContainerHeader needs, so its answer is
      // returned rather than thrown away.
      containerInfo = await trpcClient.storage.swift.getContainerMetadata.query({
        project_id: projectId,
        container: containerName,
      })
    } else {
      // One HeadBucket. Cheaper and more accurate than ListBuckets, which would miss a
      // bucket the project can read but doesn't own. Nothing in the response to reuse.
      await trpcClient.storage.ceph.containers.head.query({ project_id: projectId, bucketName: containerName })
    }
  } catch (error) {
    // Only an answer from the server is a verdict. Anything that isn't a tRPC error never
    // reached one — a broken procedure path, a bug in this file — and swallowing it would
    // turn that into a silently rendered page; let it surface.
    if (!isTRPCClientError(error)) throw error
    missing = isNotFoundResponse(error)
  }

  // Thrown outside the catch so the router's own notFound can't be swallowed by it.
  if (missing) {
    throw notFound({ data: { reason: CONTAINER_NOT_FOUND } })
  }

  return { containerInfo, fetchedAt: Date.now() }
}
