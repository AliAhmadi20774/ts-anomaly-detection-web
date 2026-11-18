import type { Request, Response } from 'express';

// Development-only demo login. This is not real authentication.
let access = '';

export default {
  'GET /api/currentUser': (_req: Request, res: Response) => {
    if (!access) {
      res.status(401).json({ success: false, errorMessage: 'Sign in required.' });
      return;
    }
    res.json({
      success: true,
      data: { name: `Demo ${access}`, userid: access, access },
    });
  },
  'POST /api/login/account': (req: Request, res: Response) => {
    const { username, password, type } = req.body;
    const valid = type === 'account' &&
      (username === 'admin' || username === 'user') && password === 'ant.design';
    access = valid ? username : '';
    res.json({
      success: true,
      status: valid ? 'ok' : 'error',
      type: 'account',
      currentAuthority: access || 'guest',
    });
  },
  'POST /api/login/outLogin': (_req: Request, res: Response) => {
    access = '';
    res.json({ success: true, data: {} });
  },
};
