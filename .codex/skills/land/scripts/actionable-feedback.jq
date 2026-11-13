def feedback_fingerprint: {
  id,
  body: (.body // ""),
  updated_at: (.updated_at // "")
};
def review_fingerprint: {
  id,
  body: (.body // ""),
  state: (.state // ""),
  submitted_at: (.submitted_at // "")
};
def actionable_review:
  select(
    (.state // "") as $state |
    ($state == "PENDING" or $state == "COMMENTED" or
     $state == "CHANGES_REQUESTED" or $state == "DISMISSED") or
    (((.body // "") | gsub("\\s"; "") | length) > 0)
  );
def human_feedback:
  select((
    (.user.login // "") == "chatgpt-codex-connector" and
    ((.body // "") | contains("codex-pull-request-review-summary"))
  ) | not);

(([ $final_inline[0][] | feedback_fingerprint ] -
  [ $preliminary_inline[0][] | feedback_fingerprint ]) | length) +
(([ $final_comments[0][] | human_feedback | feedback_fingerprint ] -
  [ $preliminary_comments[0][] | human_feedback | feedback_fingerprint ]) | length) +
(([ $final_reviews[0][] | actionable_review | review_fingerprint ] -
  [ $preliminary_reviews[0][] | actionable_review | review_fingerprint ]) | length) +
(([ $final_threads[0][] | select(.isResolved == false) | .id ] -
  [ $preliminary_threads[0][] | select(.isResolved == false) | .id ]) | length) +
([ $final_reviews[0]
   | map(select(.state == "APPROVED" or .state == "CHANGES_REQUESTED"))
   | sort_by(.submitted_at // "")
   | group_by(.user.login // "")[]
   | last
   | select(.state == "CHANGES_REQUESTED")
 ] | length)
