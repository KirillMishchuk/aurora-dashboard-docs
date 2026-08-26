import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest"
import { render, screen, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { PortalProvider } from "@cloudoperators/juno-ui-components"
import { LifecycleRulesTable } from "./LifecycleRulesTable"
import { I18nProvider } from "@lingui/react"
import { i18n } from "@lingui/core"
import { ReactNode } from "react"
import type { LifecycleRuleRead } from "@/server/Storage/types/ceph"
import { trpcReact } from "@/client/trpcClient"

/* eslint-disable @typescript-eslint/no-explicit-any */

vi.mock("@/client/trpcClient", () => ({
  trpcReact: {
    storage: {
      ceph: {
        lifecycle: {
          get: {
            useQuery: vi.fn(),
          },
          set: {
            useMutation: vi.fn(),
          },
          delete: {
            useMutation: vi.fn(),
          },
        },
      },
    },
    useUtils: vi.fn(),
  },
}))

vi.mock("@/client/hooks/useProjectId", () => ({
  useProjectId: () => "test-project-id",
}))

const Wrapper = ({ children }: { children: ReactNode }) => <I18nProvider i18n={i18n}>{children}</I18nProvider>
const PortalWrapper = ({ children }: { children: ReactNode }) => (
  <I18nProvider i18n={i18n}>
    <PortalProvider>{children}</PortalProvider>
  </I18nProvider>
)

describe("LifecycleRulesTable", () => {
  beforeAll(async () => {
    await act(async () => {
      i18n.activate("en")
    })
  })

  beforeEach(() => {
    ;(trpcReact.useUtils as any).mockReturnValue({
      storage: {
        ceph: {
          lifecycle: {
            get: {
              invalidate: vi.fn(),
            },
          },
        },
      },
    })
    ;(trpcReact.storage.ceph.lifecycle.get.useQuery as any).mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    })
    ;(trpcReact.storage.ceph.lifecycle.set.useMutation as any).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      reset: vi.fn(),
    })
    ;(trpcReact.storage.ceph.lifecycle.delete.useMutation as any).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      reset: vi.fn(),
    })
  })

  const mockOnEditRule = vi.fn()
  const mockOnToggleSelectRule = vi.fn()

  const sampleRules: LifecycleRuleRead[] = [
    {
      ID: "rule-1",
      Status: "Enabled",
      Filter: { Prefix: "logs/" },
      Expiration: { Days: 30 },
    },
    {
      ID: "rule-2",
      Status: "Disabled",
      Filter: { Prefix: "" },
      Expiration: { Days: 90 },
    },
  ]

  const sampleRulesWithIndices = sampleRules.map((rule, index) => ({ rule, originalIndex: index }))

  it("renders the column headers", () => {
    render(
      <LifecycleRulesTable
        bucketName="test-bucket"
        rulesWithIndices={sampleRulesWithIndices}
        selectedIndices={[]}
        onToggleSelectRule={mockOnToggleSelectRule}
        onEditRule={mockOnEditRule}
        canUpdateLifecycle={true}
        canDeleteLifecycle={true}
      />,
      { wrapper: Wrapper }
    )

    expect(screen.getByText("Rule ID")).toBeInTheDocument()
    expect(screen.getByText("Status")).toBeInTheDocument()
    expect(screen.getByText("Scope")).toBeInTheDocument()
    expect(screen.getByText("Expiration")).toBeInTheDocument()
    expect(screen.getByText("Noncurrent Versions")).toBeInTheDocument()
    expect(screen.getByText("Other Actions")).toBeInTheDocument()
  })

  it("renders empty state when rules array is empty", () => {
    render(
      <LifecycleRulesTable
        bucketName="test-bucket"
        rulesWithIndices={[]}
        selectedIndices={[]}
        onToggleSelectRule={mockOnToggleSelectRule}
        onEditRule={mockOnEditRule}
        canUpdateLifecycle={true}
        canDeleteLifecycle={true}
        isFiltered={false}
      />,
      { wrapper: Wrapper }
    )

    expect(screen.getByText("Rule ID")).toBeInTheDocument()
    expect(screen.getByText("There are no lifecycle rules for this bucket")).toBeInTheDocument()
  })

  it("renders actions menu button for each rule row", () => {
    render(
      <LifecycleRulesTable
        bucketName="test-bucket"
        rulesWithIndices={sampleRulesWithIndices}
        selectedIndices={[]}
        onToggleSelectRule={mockOnToggleSelectRule}
        onEditRule={mockOnEditRule}
        canUpdateLifecycle={true}
        canDeleteLifecycle={true}
      />,
      { wrapper: Wrapper }
    )

    const firstRow = screen.getByTestId("lifecycle-rule-row-0")
    const secondRow = screen.getByTestId("lifecycle-rule-row-1")

    expect(firstRow.querySelector("button[aria-haspopup='menu']")).toBeInTheDocument()
    expect(secondRow.querySelector("button[aria-haspopup='menu']")).toBeInTheDocument()
  })

  describe("Permission gating - selection column", () => {
    it("hides the Select column when canDeleteLifecycle is false", () => {
      render(
        <LifecycleRulesTable
          bucketName="test-bucket"
          rulesWithIndices={sampleRulesWithIndices}
          selectedIndices={[]}
          onToggleSelectRule={mockOnToggleSelectRule}
          onEditRule={mockOnEditRule}
          canUpdateLifecycle={true}
          canDeleteLifecycle={false}
        />,
        { wrapper: Wrapper }
      )

      expect(screen.queryByText("Select")).not.toBeInTheDocument()
    })

    it("shows the Select column when canDeleteLifecycle is true", () => {
      render(
        <LifecycleRulesTable
          bucketName="test-bucket"
          rulesWithIndices={sampleRulesWithIndices}
          selectedIndices={[]}
          onToggleSelectRule={mockOnToggleSelectRule}
          onEditRule={mockOnEditRule}
          canUpdateLifecycle={true}
          canDeleteLifecycle={true}
        />,
        { wrapper: Wrapper }
      )

      expect(screen.getByText("Select")).toBeInTheDocument()
    })
  })

  describe("Permission gating - row actions", () => {
    const openRowMenu = async (rowTestId: string) => {
      const user = userEvent.setup()
      const row = screen.getByTestId(rowTestId)
      const menuButton = row.querySelector("button[aria-haspopup='menu']") as HTMLElement
      await user.click(menuButton)
    }

    it("shows Edit Lifecycle Rule but hides Delete Lifecycle Rule when canUpdateLifecycle is true and canDeleteLifecycle is false", async () => {
      render(
        <LifecycleRulesTable
          bucketName="test-bucket"
          rulesWithIndices={sampleRulesWithIndices}
          selectedIndices={[]}
          onToggleSelectRule={mockOnToggleSelectRule}
          onEditRule={mockOnEditRule}
          canUpdateLifecycle={true}
          canDeleteLifecycle={false}
        />,
        { wrapper: PortalWrapper }
      )

      await openRowMenu("lifecycle-rule-row-0")

      expect(screen.getByText("Edit Lifecycle Rule")).toBeInTheDocument()
      expect(screen.queryByText("Delete Lifecycle Rule")).not.toBeInTheDocument()
    })

    it("shows Delete Lifecycle Rule but hides Edit Lifecycle Rule when canUpdateLifecycle is false and canDeleteLifecycle is true", async () => {
      render(
        <LifecycleRulesTable
          bucketName="test-bucket"
          rulesWithIndices={sampleRulesWithIndices}
          selectedIndices={[]}
          onToggleSelectRule={mockOnToggleSelectRule}
          onEditRule={mockOnEditRule}
          canUpdateLifecycle={false}
          canDeleteLifecycle={true}
        />,
        { wrapper: PortalWrapper }
      )

      await openRowMenu("lifecycle-rule-row-0")

      expect(screen.queryByText("Edit Lifecycle Rule")).not.toBeInTheDocument()
      expect(screen.getByText("Delete Lifecycle Rule")).toBeInTheDocument()
    })

    it("renders no row menu button when both canUpdateLifecycle and canDeleteLifecycle are false", () => {
      render(
        <LifecycleRulesTable
          bucketName="test-bucket"
          rulesWithIndices={sampleRulesWithIndices}
          selectedIndices={[]}
          onToggleSelectRule={mockOnToggleSelectRule}
          onEditRule={mockOnEditRule}
          canUpdateLifecycle={false}
          canDeleteLifecycle={false}
        />,
        { wrapper: PortalWrapper }
      )

      const firstRow = screen.getByTestId("lifecycle-rule-row-0")
      expect(firstRow.querySelector("button[aria-haspopup='menu']")).not.toBeInTheDocument()
    })
  })
})
