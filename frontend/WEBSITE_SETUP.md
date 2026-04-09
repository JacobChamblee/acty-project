# Acty Cactus Website - Setup Guide

## 📁 Project Structure

Your website has been created with the following structure:

```
frontend/
├── public/
│   └── index.html          # Web entry point
├── src/
│   ├── pages/
│   │   ├── Landing.js      # Main landing page component
│   │   └── Landing.css     # Landing page styles (UI/UX Pro Max)
│   ├── App.css             # Global app styles
│   ├── AppWeb.js           # Web app container
│   ├── indexWeb.js         # Web React DOM entry point
│   └── App.js              # Original mobile app (unchanged)
├── package.json            # Dependencies
└── README.md               # This file
```

## 🚀 Quick Start

### Option 1: Using Create React App (Recommended)

For a production-ready setup with webpack, hot reload, and optimizations:

```bash
cd c:\Users\Jacob\Desktop\acty-project
npx create-react-app website
cd website
npm install framer-motion
```

Then copy the `src/pages/Landing.js` and `src/pages/Landing.css` files from the frontend folder.

### Option 2: Using Vite (Faster Development)

For ultra-fast development with instant reload:

```bash
cd c:\Users\Jacob\Desktop\acty-project
npm create vite@latest website -- --template react
cd website
npm install
npm install framer-motion
```

Then copy the Landing page files.

### Option 3: Using Next.js (Full-Stack Ready)

For server-side rendering, API routes, and deployment:

```bash
cd c:\Users\Jacob\Desktop\acty-project
npx create-next-app@latest website
cd website
npm install framer-motion
```

## 🎨 Design System (UI/UX Pro Max)

The website uses:

- **Style**: Soft UI Evolution with Premium Feel
- **Colors**: Botanical Green + Sage palette
- **Primary**: #4CAF50 (Cactus Green)
- **Accent**: #D4AF37 (Gold)
- **Typography**: System fonts optimized for readability
- **Animations**: Framer Motion with smooth transitions
- **Spacing**: 8px base unit grid system

### Key Features Implemented:

✅ Responsive design (mobile-first)  
✅ Soft shadows and glassmorphism elements  
✅ Smooth animations and transitions  
✅ Gradient backgrounds  
✅ Premium CTAs with hover effects  
✅ Coming Soon badge with pulse animation  
✅ Feature cards with elevation on hover  
✅ Dark footer with light text  
✅ SEO-friendly structure  
✅ Accessibility compliance (WCAG AA)  

## 📱 Responsive Breakpoints

- **Mobile**: < 480px
- **Tablet**: 480px - 768px  
- **Desktop**: > 768px
- **Large Desktop**: > 1200px

## 📝 Content Sections

### 1. Hero Section
- Floating animated logo
- Value proposition headline
- "Coming Soon" badge
- Primary & secondary CTAs
- Animated gradient blobs

### 2. Value Proposition
- 4 key value cards
- Icons with descriptions
- Hover animations

### 3. How It Works
- 3-step process
- Step connectors
- Progressive reveals

### 4. Features
- 4 feature boxes with lists
- Icons and descriptions
- Checkmarks for items

### 5. Privacy Section
- Gradient background
- 3 privacy pillars
- Glassmorphic cards

### 6. Information Section
- 3 use case cards
- For owners, buyers, lenders

### 7. Early Access
- Email signup CTA
- Form validation ready

### 8. Footer
- Links and social
- Company information

## 🖼️ Logo Integration

Place your logo at:
```
public/logo.png
```

The component expects a square image (suggested: 200x200px or larger).

## 🔧 Customization

### Change Colors

Edit `src/pages/Landing.css` CSS variables at the top:

```css
--primary: #4CAF50;        /* Main green */
--sage: #66BB6A;           /* Light green */
--accent-gold: #D4AF37;    /* Accent */
```

### Modify Content

Edit `src/pages/Landing.js` - all text and structure is customizable:

```javascript
<h1 className="hero-title">
  Your custom title here
</h1>
```

### Add Sections

The component uses motion variants - copy any section and modify:

```javascript
<motion.div
  variants={containerVariants}
  initial="hidden"
  whileInView="visible"
>
  {/* Your content */}
</motion.div>
```

## 📦 Dependencies

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "framer-motion": "^latest"
  }
}
```

## 🚀 Deployment Options

### Vercel (Recommended for Next.js)
```bash
npm i -g vercel
vercel
```

### Netlify
```bash
npm run build
netlify deploy --prod --dir=build
```

### GitHub Pages
```bash
npm install --save-dev gh-pages
# Add to package.json:
# "homepage": "https://yourusername.github.io/acty-website",
# "predeploy": "npm run build",
# "deploy": "gh-pages -d build"
npm run deploy
```

## 🔐 Environment Variables

Create a `.env.local` file for sensitive data:

```
REACT_APP_API_URL=https://api.acty.com
REACT_APP_EARLY_ACCESS_ENDPOINT=/api/early-access
```

## 🧪 Testing

The component is ready for:
- Jest unit tests
- React Testing Library
- Cypress E2E tests

## 📱 Mobile Optimization

The CSS includes mobile-first responsive design with optimized:
- Font sizes (using clamp())
- Touch targets (minimum 44x44px)
- Spacing adjustments
- Navigation adaptability

## ♿ Accessibility

Features included:
- Semantic HTML
- ARIA labels
- Color contrast (WCAG AA)
- Focus states
- Keyboard navigation
- Skip links ready

## 📊 Performance

Optimizations:
- CSS-only animations where possible
- Lazy loading with Intersection Observer
- Optimized gradients
- Minimal JavaScript
- Framer Motion optimizations

## 🎯 Next Steps

1. **Set up your preferred framework** (Create React App / Vite / Next.js)
2. **Add the logo** to the public folder
3. **Customize colors** in the CSS design system
4. **Update content** with your specific details
5. **Add email capture** to the early access form
6. **Deploy** to Vercel, Netlify, or your hosting

## 🔗 Resources

- **Framer Motion**: https://www.framer.com/motion
- **UI/UX Pro Max**: https://uupm.cc
- **Notion**: https://www.notion.so/Acty-CACTUS-31ecb09f29088060a0ddc5008add3e77
- **GitHub**: https://github.com/mycactusismissing/acty-cactus

## 📞 Support

For issues or customization needs, refer to:
- Framer Motion documentation
- React documentation
- Your project's issue tracker

---

**Built with ❤️ using UI/UX Pro Max design principles and Framer Motion animations**
