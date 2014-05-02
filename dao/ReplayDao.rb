require "#{File.expand_path(File.dirname(__FILE__))}/DaoBase"
require "#{File.expand_path(File.dirname(__FILE__))}/../entity/Replay"

class ReplayDao < DaoBase
  @@version = 0.00

  # リプレイファイル情報を登録
  def insert(replay)
    inserted_replay = Replay.new
    
    res = @db.exec(<<-"SQL")
      INSERT INTO
        replays (
          game_id
        , track_record_id
        , relative_file_path
        , player1_account_id
        , player1_type1_id
        )
      VALUES (
        #{replay.game_id.to_i}
      , #{replay.track_record_id.to_i}
      , #{replay.game_id.to_i} || '/' || (currval('replays_id_seq') / 100000)::TEXT || '/' || currval('replays_id_seq') || '.rep'
      , #{replay.player1_account_id.to_i}
      , #{replay.player1_type1_id.to_i}
      )
      RETURNING
        *
    SQL
    
    res.num_fields.times do |i|
      inserted_replay.instance_variable_set("@#{res.fields[i]}", res[0][i])
    end
    
    return inserted_replay
  end
  
  
end
