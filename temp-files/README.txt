Branch: kiryl-ceph-lifecycle-rules
Base commit: 74ade1cb14396f717c930282fbfefc4c506643b2

Apply on the other machine with:
  git checkout kiryl-ceph-lifecycle-rules   # (fetch/checkout first if needed)
  git checkout 74ade1cb14396f717c930282fbfefc4c506643b2 -- .   # only if branch tip differs, otherwise skip
  git apply aurora-dashboard-wip.patch

Modified files:
M  packages/aurora/src/client/components/ListToolbar/SortInput.tsx
M  packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTab.tsx
M  packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTable.tsx
M  packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.test.tsx
M  packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.tsx
M  packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.test.tsx
M  packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.tsx
M  packages/aurora/src/locales/de/messages.po
M  packages/aurora/src/locales/de/messages.ts
M  packages/aurora/src/locales/en/messages.po
M  packages/aurora/src/locales/en/messages.ts
