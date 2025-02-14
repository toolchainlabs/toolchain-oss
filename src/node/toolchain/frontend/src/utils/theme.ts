/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import { createTheme } from '@mui/material/styles';

import TestOutcomeType from 'common/enums/TestOutcomeType';

const breakpoints = {
  values: {
    xs: 0,
    sm: 600,
    md: 960,
    lg: 1280,
    xl: 1920,
  },
};

const defaultThemeWithBreakpoints = createTheme({ breakpoints });

export default createTheme({
  ...defaultThemeWithBreakpoints,
  components: {
    MuiTextField: {
      defaultProps: {
        variant: 'standard',
      },
    },
    MuiSelect: {
      defaultProps: {
        variant: 'standard',
      },
    },
    MuiFormControl: {
      defaultProps: {
        variant: 'standard',
      },
    },
    MuiCssBaseline: {
      styleOverrides: {
        a: {
          textDecoration: 'none',
        },
        'a:hover': {
          textDecoration: 'underline',
        },
        body: {
          backgroundColor: 'rgba(245, 245, 245, 1)',
        },
        [`.${TestOutcomeType.PASSED}`]: { color: 'rgba(76, 175, 80, 1)' },
        [`.${TestOutcomeType.FAILED}`]: { color: 'rgba(244, 67, 54, 1)' },
        [`.${TestOutcomeType.ERROR}`]: { color: 'rgba(244, 67, 54, 1)' },
        [`.${TestOutcomeType.X_PASSED_STRICT}`]: { color: 'rgba(244, 67, 54, 1)' },
        [`.${TestOutcomeType.X_PASSED}`]: { color: 'rgba(255, 152, 0, 1)' },
        [`.${TestOutcomeType.X_FAILED}`]: { color: 'rgba(255, 152, 0, 1)' },
        [`.${TestOutcomeType.SKIPPED}`]: { color: 'rgba(255, 152, 0, 1)' },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'unset',
          [defaultThemeWithBreakpoints.breakpoints.down('sm')]: {
            maxWidth: '100% !important',
          },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: {
          '&$focused': {
            color: 'rgba(0, 0, 0, 0.54)',
          },
        },
      },
    },
    MuiPopover: {
      styleOverrides: {
        root: {
          [defaultThemeWithBreakpoints.breakpoints.down('sm')]: {
            zIndex: '1303 !important',
          },
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        arrow: {
          color: '#1C2B39',
        },
        tooltip: {
          backgroundColor: '#1C2B39',
          borderRadius: defaultThemeWithBreakpoints.spacing(0.5),
          padding: defaultThemeWithBreakpoints.spacing(2),
        },
      },
    },
    MuiSnackbar: {
      defaultProps: {
        ClickAwayListenerProps: {
          mouseEvent: 'onMouseDown',
          touchEvent: 'onTouchStart',
        },
      },
      styleOverrides: {
        root: {
          [`& MuiPaper-root`]: {
            boxShadow:
              '0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px rgba(0, 0, 0, 0.14), 0px 1px 18px rgba(0, 0, 0, 0.12)',
          },
          left: 'calc(50% + 40px) !important',
          [defaultThemeWithBreakpoints.breakpoints.down('md')]: {
            left: '50% !important',
          },
          [defaultThemeWithBreakpoints.breakpoints.down('sm')]: {
            left: '8px !important',
          },
        },
      },
    },
  },
  palette: {
    text: {
      primary: 'rgba(0, 0, 0, 0.87)',
      secondary: 'rgba(0, 0, 0, 0.54)',
      disabled: 'rgba(0, 0, 0, 0.38)',
    },
    primary: {
      main: 'rgba(0, 169, 183, 1)',
      dark: 'rgba(0, 115, 124, 1)',
      contrastText: 'rgba(255, 255, 255, 1)',
      light: 'rgba(0, 219, 237, 1)',
    },
    secondary: {
      main: 'rgba(191, 154, 115, 1)',
    },
    success: {
      main: 'rgba(76, 175, 80, 1)',
      dark: 'rgba(59, 135, 62, 1)',
    },
    error: { main: 'rgba(244, 67, 54, 1)' },
    warning: { main: 'rgba(255, 152, 0, 1)' },
    grey: {
      '50': 'rgba(250, 250, 250, 1)',
      '100': 'rgba(245, 245, 245, 1)',
      '200': 'rgba(238, 238, 238, 1)',
      '300': 'rgb(224, 224, 224)',
    },
    action: {
      disabled: 'rgba(0, 0, 0, 0.38)',
    },
  },
  typography: {
    body1: {
      fontFamily: 'Fira Sans, sans-serif',
      fontWeight: 400,
      fontStyle: 'normal',
      fontSize: 16,
      lineHeight: 1.5,
      letterSpacing: 0,
    },
    body2: {
      fontFamily: 'Fira Sans, sans-serif',
      fontWeight: 400,
      fontStyle: 'normal',
      fontSize: 14,
      lineHeight: 1.5,
      letterSpacing: 0,
    },
    body3: {
      fontFamily: 'Fira Sans',
      fontSize: 18,
      fontStyle: 'normal',
      fontWeight: 400,
      lineHeight: '27px',
      letterSpacing: 0,
      textAlign: 'left',
    },
    subtitle1: {
      fontFamily: 'Fira Sans, sans-serif',
      fontWeight: 500,
      fontStyle: 'normal',
      fontSize: 16,
      lineHeight: 1.5,
    },
    subtitle2: {
      fontFamily: 'Fira Sans',
      fontSize: 14,
      fontStyle: 'normal',
      fontWeight: 500,
      lineHeight: 1.5,
      letterSpacing: 0,
      textAlign: 'left',
    },
    button: {
      fontFamily: 'Fira Sans, sans-serif',
      fontWeight: 700,
      fontStyle: 'normal',
      fontSize: 14,
      letterSpacing: 1,
    },
    button1: {
      fontFamily: 'Fira Sans, sans-serif',
      fontWeight: 500,
      fontStyle: 'normal',
      fontSize: 14,
      letterSpacing: 1,
      lineHeight: '21px',
    },
    button2: {
      fontFamily: 'Fira Sans, sans-serif',
      fontWeight: 500,
      fontStyle: 'normal',
      fontSize: 12,
      letterSpacing: 1,
      lineHeight: '18px',
      textAlign: 'left',
    },
    button3: {
      fontFamily: 'Fira Sans',
      fontSize: 16,
      fontStyle: 'normal',
      fontWeight: 500,
      lineHeight: '32px',
      letterSpacing: 1,
      textAlign: 'left',
    },
    h1: {
      fontFamily: 'Fira Sans, sans-serif',
      fontWeight: 600,
      fontStyle: 'normal',
      fontSize: 48,
      lineHeight: 1.5,
      letterSpacing: 0,
      [defaultThemeWithBreakpoints.breakpoints.down('sm')]: {
        fontSize: 40,
      },
    },
    h2: {
      fontFamily: 'Fira Sans, sans-serif',
      fontWeight: 600,
      fontStyle: 'normal',
      fontSize: 32,
      lineHeight: 1.5,
      letterSpacing: 0,
    },
    h3: {
      fontFamily: 'Fira Sans, sans-serif',
      fontStyle: 'normal',
      fontSize: 24,
      fontWeight: 500,
      lineHeight: 1.2,
      letterSpacing: 0,
    },
    h4: {
      fontFamily: 'Fira Sans, sans-serif',
      fontStyle: 'normal',
      fontSize: 18,
      fontWeight: 500,
      lineHeight: 1.2,
      letterSpacing: 0,
    },
    overline: {
      fontFamily: 'Fira Sans, sans-serif',
      fontSize: 12,
      fontStyle: 'normal',
      fontWeight: 400,
      lineHeight: 1.5,
      letterSpacing: 1,
      textTransform: 'uppercase',
    },
    caption: {
      fontFamily: 'Fira Sans, sans-serif',
      fontSize: 12,
      fontStyle: 'normal',
      fontWeight: 400,
      lineHeight: 1.5,
      letterSpacing: 0,
    },
    code1: {
      fontFamily: 'Fira Code, sans-serif',
      fontSize: 14,
      fontStyle: 'normal',
      fontWeight: 450,
      lineHeight: 1.5,
      letterSpacing: 0,
    },
    code2: {
      fontFamily: 'Fira Code, sans-serif',
      fontSize: 12,
      fontStyle: 'normal',
      fontWeight: 450,
      lineHeight: 1.5,
      letterSpacing: 0,
    },
  },
});

declare module '@mui/material/styles' {
  interface TypographyVariants {
    body3: React.CSSProperties;
    button1: React.CSSProperties;
    button2: React.CSSProperties;
    button3: React.CSSProperties;
    code1: React.CSSProperties;
    code2: React.CSSProperties;
  }

  // allow configuration using `createTheme`
  interface TypographyVariantsOptions {
    body3?: React.CSSProperties;
    button1?: React.CSSProperties;
    button2?: React.CSSProperties;
    button3?: React.CSSProperties;
    code1?: React.CSSProperties;
    code2?: React.CSSProperties;
  }
}

// Update the Typography's variant prop options
declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    body3: true;
    button1: true;
    button2: true;
    button3: true;
    code1: true;
    code2: true;
  }
}
