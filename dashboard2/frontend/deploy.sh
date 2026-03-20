#!/bin/bash
# GitHub + Render 部署脚本

echo "=== Dashboard 2.0 部署指南 ==="
echo ""

# 1. 检查 Git 是否初始化
if [ ! -d ".git" ]; then
    echo "1. 初始化 Git..."
    git init
    git config user.email "your@email.com"
    git config user.name "Your Name"
else
    echo "1. Git 已初始化"
fi

# 2. 添加文件
echo "2. 添加文件..."
git add .

# 3. 提交
echo "3. 提交更改..."
git commit -m "Dashboard 2.0 - Initial release" || echo "没有新更改需要提交"

# 4. 提示用户创建 GitHub 仓库
echo ""
echo "=== 下一步：创建 GitHub 仓库 ==="
echo ""
echo "请在浏览器中完成以下步骤："
echo ""
echo "1. 访问 https://github.com/new"
echo "2. Repository name: neo-dashboard"
echo "3. 选择 'Public' 或 'Private'"
echo "4. 不要勾选 'Add a README file'"
echo "5. 点击 'Create repository'"
echo ""
echo "创建完成后，复制仓库地址，然后运行："
echo ""
echo "git remote add origin https://github.com/YOUR_USERNAME/neo-dashboard.git"
echo "git branch -M main"
echo "git push -u origin main"
echo ""
echo "=== Render 部署 ==="
echo ""
echo "代码推送到 GitHub 后："
echo "1. 访问 https://render.com"
echo "2. 用 GitHub 账号登录"
echo "3. 点击 'New +' → 'Static Site'"
echo "4. 选择 neo-dashboard 仓库"
echo "5. 配置："
echo "   - Build Command: npm install && npm run build"
echo "   - Publish Directory: dist"
echo "6. 点击 'Create Static Site'"
echo ""
