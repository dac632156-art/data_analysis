import BrandMark from './BrandMark';

interface AuthBrandLogoProps {
  size?: number;
  shape?: 'circle' | 'rounded';
}

/**
 * 登录 / 注册卡 / CoverPage 品牌 logo（圆形，蓝紫斜杠渐变）。
 */
export default function AuthBrandLogo({
  size = 36,
  shape = 'circle',
}: AuthBrandLogoProps) {
  return <BrandMark size={size} shape={shape} />;
}
