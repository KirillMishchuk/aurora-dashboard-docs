import { ReactNode } from "react"
import { NotificationOptions } from "@cloudoperators/juno-ui-components"
import { Trans } from "@lingui/react/macro"

type ToastReturnType = { message: ReactNode } & NotificationOptions

export const getCredentialDeletedToast = (accessKey: string): ToastReturnType => ({
  message: <Trans>Access key deleted</Trans>,
  description: <Trans>Access key "{accessKey}" was permanently deleted.</Trans>,
})
