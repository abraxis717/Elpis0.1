# Release guard closure rule

No guard merges without a mutation test that demonstrates its negative branch
firing for the intended reason, and that mutation must previously have been
shown to pass against the unpatched guard. Record the source revision, mutation,
exit status, and diagnostic. A nonzero exit for an unrelated reason is
`WRONG_GUARD_FIRED`, never qualification.

Keep a clean positive control. Run the permanent regression in CI. For newly
introduced controls, also disable the specific control in an isolated copy and
show that the regression detects its absence. Unit isolation does not replace
installed-package and native transaction qualification.

Seal only after implementation qualification. A provisional seal is confined to
an explicit throwaway copy and makes no correctness claim. Historical release
manifests and tags are immutable. Push the qualified main commit and require its
push workflows to pass before creating the annotated tag and public release.
