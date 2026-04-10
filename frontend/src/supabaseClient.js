import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL  = process.env.REACT_APP_SUPABASE_URL  || '';
const SUPABASE_ANON = process.env.REACT_APP_SUPABASE_ANON_KEY || '';

if (!SUPABASE_URL || SUPABASE_URL.includes('placeholder')) {
  console.warn('[Supabase] REACT_APP_SUPABASE_URL is not set — auth will not work. See frontend/.env');
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON);
