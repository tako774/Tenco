# trip.rb version 0.0.4
# 2003-01-12T07:50:59+9:00
# 2ch trip 8 or 10 or other! 
# Copyright (c) 2002-2003 Igarashi Makoto (raccy)
# You can redistribute it and/or modify it under the same term as Ruby.

module Trip
  VERSION = "0.0.4"
  
  module_function
  
  def trip(str, n = 8)
    unless (1..11) === n
      raise ArgumentError, "trip's figure must be within 1..11"
    end
    str.crypt(salt(str))[-n, n]
  end
  
  def trip8(str)
    trip(str, 8)
  end

  def trip10(str)
    trip(str, 10)
  end

  def salt(str)
    if str.empty?
      raise ArgumentError, "arg must not be empty String"
    end
    (str + "H.")[1,2].
        gsub(/[^\.-z]/, ".").
        tr(":;<=>?@[\\\\]^_`", "ABCDEFGabcdef")
  end
  
end

class String
  def trip(n = 8)
    Trip.trip(self, n)
  end
  def trip8
    trip(8)
  end
  def trip10
    trip(10)
  end
end


