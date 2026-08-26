/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingIncludes: {
    "/api/chat": ["./lib/persona_prompt.txt"],
  },
};

export default nextConfig;
