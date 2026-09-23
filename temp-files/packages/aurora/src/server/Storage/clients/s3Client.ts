import { S3Client } from "@aws-sdk/client-s3"
import { S3_CONNECTION_TIMEOUT_MS } from "../constants"

/**
 * Creates an S3Client configured for Ceph RGW.
 * forcePathStyle is required for Ceph — it does not support virtual-hosted-style URLs.
 *
 * @param access - AWS access key ID
 * @param secret - AWS secret access key
 * @param endpoint - S3 endpoint URL (required)
 * @param region - AWS region (default: "default")
 */
export function createS3Client(access: string, secret: string, endpoint: string, region = "default"): S3Client {
  if (!access?.trim()) {
    throw new Error("S3 access key is required")
  }
  if (!secret?.trim()) {
    throw new Error("S3 secret key is required")
  }
  if (!endpoint?.trim()) {
    throw new Error("S3 endpoint is required")
  }

  return new S3Client({
    region,
    endpoint,
    credentials: {
      accessKeyId: access,
      secretAccessKey: secret,
    },
    forcePathStyle: true,
    // `connectionTimeout` only bounds establishing the TCP connection — it does not touch an
    // already-open socket, so it's safe for the streaming download/upload procedures that
    // share this client (objectRouter.ts downloadObject/uploadObject). A hung connect to RGW
    // now fails fast instead of hanging until the platform's keep-alive timeout.
    //
    // `requestTimeout` (socket-inactivity timeout) and `maxAttempts` (retry count, default 3)
    // are deliberately left untouched here: both are shared by every Ceph procedure including
    // long-running streams, and need their own investigation against the pinned SDK version
    // before being changed globally — tracked as a separate ticket. Cancelling a long scan is
    // instead handled by `ctx.req.signal` plus the page ceiling on the version-scan loops.
    requestHandler: {
      connectionTimeout: S3_CONNECTION_TIMEOUT_MS,
    },
  })
}
