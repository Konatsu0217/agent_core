echo "🔍 正在搜索所有名为 'logs' 的文件夹..."
echo "ℹ️  注意: .git 目录下的 logs 将被保留"
echo ""

# 查找所有名为 logs 的文件夹（排除 .git 目录）
logs_dirs=$(find . -type d -name "logs" -not -path "*/.git/*" 2>/dev/null)

# 检查是否找到
if [ -z "$logs_dirs" ]; then
    echo "✅ 未找到任何 'logs' 文件夹"
    exit 0
fi

# 显示找到的文件夹
echo "📁 找到以下 'logs' 文件夹："
echo "================================"
echo "$logs_dirs" | nl
echo "================================"
echo ""

# 统计数量
count=$(echo "$logs_dirs" | wc -l | tr -d ' ')
echo "📊 共找到 $count 个 'logs' 文件夹"
echo ""

# 询问是否删除
read -p "⚠️  确认删除这些文件夹吗? (yes/no): " confirm

if [ "$confirm" = "yes" ] || [ "$confirm" = "y" ]; then
    echo ""
    echo "🗑️  开始删除..."

    # 逐个删除并显示进度
    i=1
    echo "$logs_dirs" | while read -r dir; do
        if [ -d "$dir" ]; then
            echo "[$i/$count] 删除: $dir"
            rm -rf "$dir"
            i=$((i + 1))
        fi
    done

    echo ""
    echo "✅ 删除完成！"
else
    echo ""
    echo "❌ 操作已取消"
    exit 0
fi