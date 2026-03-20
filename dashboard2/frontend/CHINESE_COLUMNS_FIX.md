# Dashboard 中文列名修复说明

## 问题
Results 表格列名显示英文而不是中文。

## 解决方案
代码本身已经有中文映射（`formatHeader` 函数里的 `translations` 对象），问题通常是：

1. **浏览器缓存** → 强制刷新 `Cmd+Shift+R`
2. **Vite 热更新失效** → 重启 dev server
3. **端口冲突** → 检查是不是连到了旧端口

## 当前状态
- Vite dev server: http://localhost:3001
- 构建文件已更新，包含中文翻译

## 代码位置
中文映射在 `App.tsx` 的 `ResultsTable` 组件里的 `formatHeader` 函数：

```typescript
const translations: Record<string, string> = {
  'stock_code': '代码',
  'stock_name': '名称',
  'close_price': '收盘价',
  'pct_change': '涨幅%',
  'turnover': '换手率%',
  // ... 更多字段
}
```

如果还有问题，检查后端返回的字段名是否匹配这些 key。
