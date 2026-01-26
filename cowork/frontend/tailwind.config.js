/** @type {import('tailwindcss').Config} */
export default {
    darkMode: ["class"],
    content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
  	extend: {
  		colors: {
  			dark: {
  				bg: '#1C1C1C',
  				surface: '#252525',
  				elevated: '#2D2D2D',
  				border: 'rgba(255, 255, 255, 0.08)'
  			},
  			warm: {
  				bg: '#F5E8D8',
  				beige: '#F5E8D8'
  			},
  			burnt: {
  				DEFAULT: '#FF4500',
  				light: 'rgba(255, 69, 0, 0.15)'
  			},
  			ink: {
  				DEFAULT: '#F5E8D8',
  				muted: 'rgba(245, 232, 216, 0.6)',
  				subtle: 'rgba(245, 232, 216, 0.4)',
  				faint: 'rgba(245, 232, 216, 0.15)'
  			},
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			}
  		},
  		fontFamily: {
  			sans: [
  				'SF Pro Display',
  				'-apple-system',
  				'BlinkMacSystemFont',
  				'sans-serif'
  			]
  		},
  		transitionTimingFunction: {
  			smooth: 'cubic-bezier(0.22, 1, 0.36, 1)'
  		},
  		animation: {
  			'scale-in': 'scaleIn 0.15s ease-out forwards',
  			'fade-in': 'fadeIn 0.3s ease-out forwards',
  			'slide-up': 'slideUp 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards'
  		},
  		keyframes: {
  			scaleIn: {
  				'0%': {
  					opacity: '0',
  					transform: 'scale(0.96)'
  				},
  				'100%': {
  					opacity: '1',
  					transform: 'scale(1)'
  				}
  			},
  			fadeIn: {
  				'0%': {
  					opacity: '0'
  				},
  				'100%': {
  					opacity: '1'
  				}
  			},
  			slideUp: {
  				'0%': {
  					opacity: '0',
  					transform: 'translateY(10px)'
  				},
  				'100%': {
  					opacity: '1',
  					transform: 'translateY(0)'
  				}
  			}
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
}
