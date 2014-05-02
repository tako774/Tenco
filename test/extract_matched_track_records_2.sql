COPY (
  SELECT
    EXTRACT(EPOCH FROM rep_timestamp)
  , player1_account_id
  , player2_account_id
  , player1_type1_id
  , player2_type1_id
  , player1_points
  , player2_points
  FROM
    track_records
  WHERE
        id > matched_track_record_id
    AND game_id = 2
  ORDER BY
    rep_timestamp
)
TO
  '/tmp/matched_2'
WITH (
  FORMAT 'csv'
, DELIMITER ','
, HEADER false
)
