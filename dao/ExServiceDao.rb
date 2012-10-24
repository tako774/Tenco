require "#{File.expand_path(File.dirname(__FILE__))}/DaoBase"
require "#{File.expand_path(File.dirname(__FILE__))}/../entity/ExService"

class ExServiceDao < DaoBase
  
  # 外部サービス情報を名前を条件として取得
  def get_by_name(name)
    ex_service = ExService.new
    
    res = @db.exec(<<-"SQL")
      SELECT
        id, name
      FROM
        ex_services
      WHERE
        name = #{s name}
    SQL
    
    res.num_fields.times do |i|
      ex_service.instance_variable_set("@#{res.fields[i]}", res[0][i])
    end
    
    return ex_service
  end
  
end
