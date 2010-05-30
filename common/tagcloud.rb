# Author: Masaki Yatsu <yatsu@yatsu.info>

class TagCloud
  def initialize
    @counts = Hash.new
    @urls = Hash.new
  end

  def add(tag, url, count)
    @counts[tag] = count
    @urls[tag] = url
  end

  def css
    text = "" 
    for level in 0..24
      font = 12 + level
      text << "span.tagcloud#{level} {font-size: #{font}px;}\n" 
      text << "span.tagcloud#{level} a {text-decoration: none;}\n" 
    end
    text
  end

  def html(limit = nil)
    tags = @counts.sort_by {|a, b| b }.reverse.map {|a, b| a }
    tags = tags[0..limit-1] if limit
    if tags.empty?
      return "" 
    elsif tags.size == 1
      tag = tags[0]
      url = @urls[tag]
      return %{<span class="tagcloud24"><a href="#{url}">#{tag}</a></span>\n}
    end

    min = Math.sqrt(@counts[tags.last])
    max = Math.sqrt(@counts[tags.first])
    factor = 0

    # special case all tags having the same count
    if max - min == 0
      min = min - 24
      factor = 1
    else
      factor = 24 / (max - min)
    end

    html = "" 
    tags.sort.each do |tag|
      count = @counts[tag]
      url   = @urls[tag]
      level = ((Math.sqrt(count) - min) * factor).to_i
      html << %{<span class="tagcloud#{level}"><a href="#{url}">#{tag}</a></span>\n}
    end
    html
  end

  def html_and_css(limit = nil)
    "<style>\n#{self.css}</style>\n#{self.html(limit)}" 
  end
end
