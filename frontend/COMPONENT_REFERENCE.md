# Acty Cactus Website - Component Reference

## Landing Component Structure

### Main Component: `<Landing />`

Complete landing page with all sections and animations.

```javascript
import Landing from './pages/Landing';
import './pages/Landing.css';

<Landing />
```

## Sub-Components

### 1. ValueCard

Displays a single value proposition with icon.

**Props:**
- `icon` (string): Emoji or text icon
- `title` (string): Card title
- `description` (string): Card description
- `variants` (object): Framer Motion animation variants

**Usage:**
```javascript
<ValueCard
  icon="🔒"
  title="Your Data, Your Rules"
  description="Encrypted, owner-controlled vehicle data."
  variants={itemVariants}
/>
```

### 2. StepCard

Shows a step in the "How It Works" section.

**Props:**
- `step` (string): Step number
- `title` (string): Step title
- `description` (string): Step description
- `color` (string): Hex color for step number
- `variants` (object): Animation variants

**Usage:**
```javascript
<StepCard
  step="1"
  title="Connect Your Vehicle"
  description="Use your OBD-II adapter..."
  color="#4CAF50"
  variants={itemVariants}
/>
```

### 3. FeatureBox

Card showing features with checkmarks.

**Props:**
- `title` (string): Feature box title
- `items` (array): Array of feature strings

**Usage:**
```javascript
<FeatureBox
  title="Real-Time Monitoring"
  items={[
    "Live OBD-II data streaming",
    "Performance metrics tracking"
  ]}
/>
```

### 4. InfoCard

Information card for different use cases.

**Props:**
- `title` (string): Card title
- `description` (string): Card description
- `variants` (object): Animation variants

**Usage:**
```javascript
<InfoCard
  title="For Vehicle Owners"
  description="Know your car's true condition..."
  variants={itemVariants}
/>
```

## Animation Variants

### containerVariants

Staggered animation for parent containers.

```javascript
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.2,
      delayChildren: 0.3,
    },
  },
};
```

### itemVariants

Fade and slide animation for individual items.

```javascript
const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.8, ease: "easeOut" },
  },
};
```

### floatingVariants

Continuous floating animation for logo.

```javascript
const floatingVariants = {
  initial: { y: 0 },
  animate: {
    y: [-10, 10, -10],
    transition: {
      duration: 4,
      repeat: Infinity,
      ease: "easeInOut",
    },
  },
};
```

## Sections Breakdown

### Hero Section
- Logo with floating animation
- Main headline with gradient
- Subtitle
- Coming Soon badge with pulse
- Primary & secondary buttons
- Animated background blobs

**Classes**: `.hero`, `.hero-content`, `.hero-title`, `.hero-subtitle`

### Value Section
- Header text
- 4-column grid of value cards
- Hover elevation effect

**Classes**: `.value-section`, `.value-grid`, `.value-card`

### How It Works
- Section header
- 3 step cards with connectors
- Responsive layout

**Classes**: `.how-it-works`, `.steps-container`, `.step-card`

### Features Section
- 4 feature boxes in grid
- Checkmarks for each item
- Hover effects

**Classes**: `.features-section`, `.features-grid`, `.feature-box`

### Privacy Section
- Gradient background
- 3 privacy pillars with icons
- Glassmorphic cards

**Classes**: `.privacy-section`, `.privacy-features`, `.privacy-item`

### Information Section
- 3 use case cards (owners, buyers, lenders)
- Staggered reveals

**Classes**: `.info-section`, `.info-content`, `.info-card`

### Early Access
- Email input form
- Notification CTA
- Readable width

**Classes**: `.early-access`, `.email-form`

### Footer
- 3-column layout
- Links and contact
- Copyright

**Classes**: `.footer`, `.footer-content`, `.footer-section`

## Navigation

Fixed navbar with:
- Brand logo and text
- Navigation links with underline animation
- Glassmorphic background
- Sticky positioning

**Classes**: `.navbar`, `.nav-brand`, `.nav-links`

## Styling System

### CSS Variables (Customizable)

```css
/* Colors */
--primary: #4CAF50;
--sage: #66BB6A;
--accent-gold: #D4AF37;

/* Shadows */
--shadow-sm: 0 4px 15px rgba(46, 125, 50, 0.08);
--shadow-md: 0 8px 30px rgba(46, 125, 50, 0.12);

/* Spacing */
--spacing-xs: 0.5rem;
--spacing-sm: 1rem;
--spacing-md: 1.5rem;
--spacing-lg: 2.5rem;
--spacing-xl: 4rem;

/* Transitions */
--transition-fast: 200ms cubic-bezier(...);
--transition-smooth: 300ms cubic-bezier(...);
```

## Button Styles

### Primary Button
- Gradient background
- Box shadow on hover
- Elevation on click

**Class**: `.btn-primary`

### Secondary Button
- Outlined style
- Border color matches primary
- Transparent background

**Class**: `.btn-secondary`

### Form Elements
- Input with focus states
- Smooth transitions
- Box shadow on focus

**Class**: `.email-form input`

## Responsive Design

### Mobile (< 480px)
- Single column layouts
- Adjusted font sizes
- Reduced spacing
- Full-width inputs

### Tablet (480px - 768px)
- 2 column grids
- Medium spacing
- Adjusted padding

### Desktop (> 768px)
- Multi-column grids
- Full spacing
- Optimized widths

### Large Desktop (> 1200px)
- Full feature set
- Maximum width containers
- Optimal spacing

## Media Queries

```css
@media (max-width: 768px) { /* Tablet and below */ }
@media (max-width: 480px) { /* Mobile */ }
```

## Performance Tips

1. **Image Optimization**: Compress logo to <100KB
2. **Animation Throttling**: Framer Motion handles this automatically
3. **Lazy Loading**: Use `whileInView` for scroll animations
4. **CSS Optimization**: Leverage CSS variables for theming
5. **Font Loading**: System fonts are fast-loading

## Browser Support

- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support
- IE: Not supported (modern design)

## Accessibility Features

✅ Semantic HTML  
✅ Color contrast (WCAG AA)  
✅ Focus states visible  
✅ Keyboard navigable  
✅ Screen reader friendly  
✅ Reduced motion respected  

## Customization Examples

### Change Primary Color
Edit CSS variable:
```css
--primary: #Your-Color;
```

### Modify Animation Speed
Edit transition:
```css
--transition-smooth: 500ms cubic-bezier(0.4, 0, 0.2, 1);
```

### Add New Section
Copy existing pattern:
```javascript
<motion.section 
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.8 }}
  viewport={{ once: true }}
>
  {/* Your content */}
</motion.section>
```

## Event Handlers (Ready to Implement)

### Early Access Form
```javascript
onSubmit={(e) => {
  e.preventDefault();
  // Add API call to save email
  // POST /api/early-access
}}
```

### Button Clicks
```javascript
onClick={() => {
  // Navigate or trigger action
}}
```

## Integration Points

### Backend API
- Email signup endpoint
- Contact form submission
- Analytics tracking

### Third-party Services
- Email service (SendGrid, Mailchimp)
- Analytics (Google Analytics, Mixpanel)
- Monitoring (Sentry, LogRocket)

## File Dependencies

```
Landing.js
├── framer-motion ✅ Installed
├── Landing.css (inline)
├── ValueCard (inline)
├── StepCard (inline)
├── FeatureBox (inline)
└── InfoCard (inline)
```

All components are self-contained in `Landing.js`. No external component libraries required.

---

**Ready to use. Fully responsive. Production-ready animations.**
