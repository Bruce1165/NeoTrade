/**
 * Robust Date Utilities - Bulletproof date handling
 * All dates are handled as YYYY-MM-DD internally
 */

/**
 * Get today's date in YYYY-MM-DD format
 */
export function getToday(): string {
  return new Date().toISOString().split('T')[0];
}

/**
 * Get yesterday's date in YYYY-MM-DD format
 */
export function getYesterday(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().split('T')[0];
}

/**
 * Ensure a date string is in YYYY-MM-DD format
 * Handles: Date objects, YYYY-MM-DD, YYYY/MM/DD, YYYYMMDD, timestamps
 */
export function toISODate(date: string | Date | number): string {
  if (!date) return '';
  
  // Already in YYYY-MM-DD format
  if (typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return date;
  }
  
  // YYYY/MM/DD format
  if (typeof date === 'string' && /^\d{4}\/\d{2}\/\d{2}$/.test(date)) {
    return date.replace(/\//g, '-');
  }
  
  // YYYYMMDD format
  if (typeof date === 'string' && /^\d{8}$/.test(date)) {
    return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
  }
  
  // Date object or timestamp
  const d = date instanceof Date ? date : new Date(date);
  if (!isNaN(d.getTime())) {
    return d.toISOString().split('T')[0];
  }
  
  console.warn('Invalid date:', date);
  return '';
}

/**
 * Format a date for display (localized)
 */
export function formatDisplayDate(date: string | Date): string {
  const isoDate = toISODate(date);
  if (!isoDate) return '';
  
  const [year, month, day] = isoDate.split('-');
  // Return in local format: YYYY/MM/DD for CN, MM/DD/YYYY for US, etc.
  const locale = navigator.language || 'zh-CN';
  if (locale.startsWith('zh')) {
    return `${year}/${month}/${day}`;
  }
  return `${month}/${day}/${year}`;
}

/**
 * Validate if string is a valid date (YYYY-MM-DD format)
 */
export function isValidDate(date: string): boolean {
  if (!date || typeof date !== 'string') return false;
  
  // Check format
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
  
  // Check if valid date
  const d = new Date(date);
  return !isNaN(d.getTime());
}

/**
 * Format date for API calls - always returns YYYY-MM-DD
 * This is the SINGLE function used before all API calls
 */
export function formatDate(date: string | Date): string {
  return toISODate(date);
}

/**
 * Get default date (yesterday) for screener runs
 */
export function getDefaultDate(): string {
  return getYesterday();
}

/**
 * Format stock code - remove .SH/.SZ suffix, ensure 6 digits
 */
export function formatStockCode(code: string): string {
  if (!code) return '';
  
  const str = String(code).trim();
  const clean = str.replace(/\.(SH|SZ|sh|sz)$/i, '');
  
  if (/^\d{6}$/.test(clean)) {
    return clean;
  }
  
  console.warn('Invalid stock code:', code);
  return clean;
}

/**
 * Validate stock code format (6 digits)
 */
export function isValidStockCode(code: string): boolean {
  return /^\d{6}$/.test(formatStockCode(code));
}

/**
 * Convert to iFind format (adds .SH or .SZ)
 */
export function toIfindCode(code: string): string {
  const clean = formatStockCode(code);
  if (!clean) return '';
  return clean.startsWith('6') ? `${clean}.SH` : `${clean}.SZ`;
}

/**
 * Parse date from input value
 * Handles browser inconsistencies with date inputs
 */
export function parseDateInput(value: string): string {
  // HTML5 date input should return YYYY-MM-DD
  // But some browsers might return localized format
  return toISODate(value);
}

/**
 * Get max date for date input (today)
 */
export function getMaxDate(): string {
  return getToday();
}

/**
 * Get min date for date input
 */
export function getMinDate(): string {
  return '2024-01-01';
}
