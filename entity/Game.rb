class Game
  attr_accessor :id, :created_at, :updated_at, :lock_version
  attr_accessor :name, :min_version, :max_version, :match_end_at, :match_start_at
  attr_accessor :is_batch_target, :is_show_stats, :is_noindex
  attr_accessor :ranking_limit_ratings_deviation, :ranking_min_matched_accounts
  attr_accessor :type1_segment_id, :type2_segment_id
end
