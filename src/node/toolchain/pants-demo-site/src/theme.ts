/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { createTheme } from '@mui/material/styles';

export default createTheme({
  palette: {
    background: {
      default: 'rgba(4, 78, 243, 0.08)',
    },
    primary: {
      main: 'rgba(4, 78, 243, 1)',
      light: 'rgba(144, 202, 255, 1)',
      dark: 'rgba(29, 66, 150, 1)',
    },
    text: {
      primary: 'rgba(0, 0, 0, 0.87)',
      secondary: 'rgba(0, 0, 0, 0.54)',
      disabled: 'rgba(0, 0, 0, 0.38)',
    },
    grey: {
      [100]: 'rgba(245, 245, 245, 1)',
    },
  },
  typography: {
    body1: {
      fontFamily: 'Fira Sans',
      fontSize: 16,
      fontWeight: 400,
      lineHeight: '24px',
      letterSpacing: 0,
      textAlign: 'left',
    },
    body2: {
      fontFamily: 'Fira Sans',
      fontSize: 14,
      fontWeight: 400,
      lineHeight: '21px',
      letterSpacing: 0,
      textAlign: 'left',
    },
    body3: {
      fontFamily: 'Fira Sans',
      fontSize: 18,
      fontWeight: 400,
      lineHeight: '27px',
      letterSpacing: 0,
      textAlign: 'center',
    },
    button: {
      fontFamily: 'Fira Sans',
      fontSize: 12,
      fontWeight: 500,
      lineHeight: '18px',
      letterSpacing: 1,
      textAlign: 'left',
    },
    button3: {
      fontFamily: 'Fira Sans',
      fontSize: 16,
      fontWeight: 500,
      lineHeight: '32px',
      letterSpacing: 1,
      textAlign: 'left',
    },
    h2: {
      fontFamily: 'Fira Sans',
      fontSize: 32,
      fontWeight: 600,
      lineHeight: '48px',
      letterSpacing: '0px',
      textAlign: 'center',
    },
    h3: {
      fontFamily: 'Fira Sans',
      fontStyle: 'normal',
      fontWeight: 500,
      fontSize: 24,
      lineHeight: '120%',
    },
    caption: {
      fontFamily: 'Fira Sans',
      fontStyle: 'normal',
      fontWeight: 400,
      fontSize: 12,
      lineHeight: '18px',
    },
    subtitle1: {
      fontFamily: 'Fira Sans',
      fontSize: 16,
      fontWeight: 500,
      lineHeight: '24px',
      letterSpacing: 0,
      textAlign: 'left',
    },
    overline: {
      fontFamily: 'Fira Sans',
      fontSize: 12,
      fontWeight: 400,
      lineHeight: '18px',
      letterSpacing: 1,
      textAlign: 'left',
    },
  },
  components: {
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: 'rgba(28, 43, 57, 1)',
        },
        arrow: {
          color: 'rgba(28, 43, 57, 1)',
        },
      },
    },
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#fff',
        },
        a: {
          textDecoration: 'none !important',
        },
      },
    },
  },
  breakpoints: {
    values: {
      xs: 0,
      sm: 400,
      md: 900,
      lg: 1280,
      xl: 1920,
    },
  },
});

declare module '@mui/material/styles' {
  interface TypographyVariants {
    body3: React.CSSProperties;
    button3: React.CSSProperties;
  }

  // allow configuration using `createTheme`
  interface TypographyVariantsOptions {
    body3?: React.CSSProperties;
    button3?: React.CSSProperties;
  }
}

// Update the Typography's variant prop options
declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    body3: true;
    button3: true;
  }
}
