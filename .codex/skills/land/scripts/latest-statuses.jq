# GitHub's commit-status history is reverse chronological. Preserve the first
# record for each context so obsolete pending or failed states cannot override
# that context's newest result.
reduce .[] as $status
  ({};
    if has($status.context)
    then .
    else .[$status.context] = $status
    end
  )
| [.[]]
