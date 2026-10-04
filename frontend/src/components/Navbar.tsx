import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button, Badge, Icon } from './ui';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isProfileDropdownOpen, setIsProfileDropdownOpen] = useState(false);
  const profileDropdownRef = useRef<HTMLDivElement | null>(null);

  const handleLogout = () => {
    setIsMobileMenuOpen(false);
    setIsProfileDropdownOpen(false);
    logout();
    navigate('/login');
  };

  // Close profile dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        profileDropdownRef.current &&
        !profileDropdownRef.current.contains(event.target as Node)
      ) {
        setIsProfileDropdownOpen(false);
      }
    };

    if (isProfileDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isProfileDropdownOpen]);

  // Close menus on route change
  useEffect(() => {
    setIsProfileDropdownOpen(false);
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  const getRoleBadgeVariant = (role?: string): 'dark' | 'neutral' | 'outline' => {
    switch (role) {
      case 'admin':
        return 'dark';
      case 'grader':
        return 'neutral';
      default:
        return 'outline';
    }
  };

  const isActiveLink = (path: string) => location.pathname === path;

  return (
    <header className="sticky top-0 z-50 w-full border-b border-zinc-200/80 bg-[#fdf8f8]/95 backdrop-blur-xl transition-colors">
      <nav
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between"
        id="main-navigation"
      >
        {/* Brand Logo */}
        <Link
          to="/"
          className="flex items-center gap-2.5 text-on-surface no-underline group"
          id="nav-brand-logo"
          onClick={() => setIsMobileMenuOpen(false)}
        >
          <div className="w-7 h-7 rounded-full bg-primary text-on-primary flex items-center justify-center shadow-xs">
            <Icon name="verified_user" size={15} />
          </div>
          <span className="font-semibold text-sm tracking-tight text-primary flex items-center gap-1">
            Proctor<span className="text-zinc-500 font-normal">AI</span>
          </span>
        </Link>

        {/* Unauthenticated In-Page Anchor Links (Desktop) */}
        {!isAuthenticated && (
          <div className="hidden md:flex items-center gap-6">
            <a
              href="#features"
              onClick={(e) => {
                if (location.pathname === '/') {
                  e.preventDefault();
                  document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
                }
              }}
              className="text-xs font-medium text-zinc-600 hover:text-zinc-900 transition-colors"
            >
              Features
            </a>
            <a
              href="#how-it-works"
              onClick={(e) => {
                if (location.pathname === '/') {
                  e.preventDefault();
                  document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' });
                }
              }}
              className="text-xs font-medium text-zinc-600 hover:text-zinc-900 transition-colors"
            >
              How it works
            </a>
            <Link
              to="/about"
              className={`text-xs font-medium transition-colors ${
                isActiveLink('/about')
                  ? 'text-primary font-semibold'
                  : 'text-zinc-600 hover:text-zinc-900'
              }`}
            >
              About
            </Link>
          </div>
        )}

        {/* Desktop Navigation Links */}
        <div className="flex items-center gap-6">
          {isAuthenticated && user ? (
            <>
              <div className="hidden md:flex items-center gap-5">
                <Link
                  to="/dashboard"
                  className={`text-xs font-medium transition-colors ${
                    isActiveLink('/dashboard')
                      ? 'text-primary font-semibold'
                      : 'text-secondary hover:text-primary'
                  }`}
                >
                  Dashboard
                </Link>

                <Link
                  to="/exams"
                  className={`text-xs font-medium transition-colors ${
                    isActiveLink('/exams')
                      ? 'text-primary font-semibold'
                      : 'text-secondary hover:text-primary'
                  }`}
                >
                  Assessments
                </Link>

                {user.role === 'admin' && (
                  <Link
                    to="/admin/exams"
                    className={`text-xs font-medium transition-colors ${
                      isActiveLink('/admin/exams')
                        ? 'text-primary font-semibold'
                        : 'text-secondary hover:text-primary'
                    }`}
                  >
                    Console
                  </Link>
                )}

                <Link
                  to="/about"
                  className={`text-xs font-medium transition-colors ${
                    isActiveLink('/about')
                      ? 'text-primary font-semibold'
                      : 'text-secondary hover:text-primary'
                  }`}
                >
                  About
                </Link>

                <Link
                  to="/help"
                  className={`text-xs font-medium transition-colors ${
                    isActiveLink('/help')
                      ? 'text-primary font-semibold'
                      : 'text-secondary hover:text-primary'
                  }`}
                >
                  Help
                </Link>
              </div>

              {/* User Identity & Dropdown (Replaces plain logout button) */}
              <div className="hidden md:block relative pl-4 border-l border-zinc-200" ref={profileDropdownRef}>
                <button
                  type="button"
                  id="user-profile-menu-button"
                  onClick={() => setIsProfileDropdownOpen(!isProfileDropdownOpen)}
                  aria-expanded={isProfileDropdownOpen}
                  aria-haspopup="true"
                  className="flex items-center gap-2.5 p-1.5 rounded-xl hover:bg-surface-container-low transition-colors text-left focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <div className="flex flex-col items-end">
                    <span className="text-xs font-semibold text-primary leading-tight">{user.name}</span>
                    <span className="text-[11px] text-zinc-500 leading-tight">{user.email}</span>
                  </div>
                  <Badge variant={getRoleBadgeVariant(user.role)} size="xs" className="capitalize">
                    {user.role}
                  </Badge>
                  <Icon
                    name={isProfileDropdownOpen ? 'expand_less' : 'expand_more'}
                    size={16}
                    className="text-secondary"
                  />
                </button>

                {/* Profile Dropdown Menu */}
                {isProfileDropdownOpen && (
                  <div
                    id="user-profile-dropdown"
                    className="absolute right-0 mt-2 w-56 rounded-2xl bg-surface-container-lowest border border-outline-variant/80 shadow-elevation p-2 space-y-1 animate-in fade-in slide-in-from-top-2 z-50"
                  >
                    {/* User Header */}
                    <div className="px-3 py-2 border-b border-outline-variant/50">
                      <div className="text-xs font-semibold text-primary truncate">{user.name}</div>
                      <div className="text-[11px] text-secondary truncate">{user.email}</div>
                      <div className="mt-1.5">
                        <Badge variant={getRoleBadgeVariant(user.role)} size="xs" className="capitalize">
                          {user.role} Account
                        </Badge>
                      </div>
                    </div>

                    {/* Settings Shortcut */}
                    <Link
                      to="/settings"
                      id="dropdown-settings-link"
                      onClick={() => setIsProfileDropdownOpen(false)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-primary hover:bg-surface-container transition-colors"
                    >
                      <Icon name="settings" size={16} className="text-secondary" />
                      <span>Settings</span>
                    </Link>

                    {/* Help Shortcut */}
                    <Link
                      to="/help"
                      onClick={() => setIsProfileDropdownOpen(false)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-primary hover:bg-surface-container transition-colors"
                    >
                      <Icon name="help" size={16} className="text-secondary" />
                      <span>Help & Support</span>
                    </Link>

                    {/* Privacy Policy */}
                    <Link
                      to="/privacy"
                      onClick={() => setIsProfileDropdownOpen(false)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-primary hover:bg-surface-container transition-colors"
                    >
                      <Icon name="shield" size={16} className="text-secondary" />
                      <span>Privacy Policy (DPDP)</span>
                    </Link>

                    <div className="border-t border-outline-variant/50 pt-1">
                      <button
                        type="button"
                        id="dropdown-logout-button"
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium text-rose-800 hover:bg-rose-50 transition-colors text-left"
                      >
                        <Icon name="logout" size={16} className="text-rose-800" />
                        <span>Log out</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Mobile Hamburger Button */}
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="md:hidden p-1.5 rounded-lg text-primary hover:bg-surface-container transition-colors"
                aria-label="Toggle Navigation Menu"
              >
                <Icon name={isMobileMenuOpen ? 'close' : 'menu'} size={20} />
              </button>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Link to="/about" className="md:hidden text-xs font-medium text-zinc-600 mr-2">
                About
              </Link>
              <Link to="/login">
                <Button variant="secondary" size="sm" id="nav-login-btn" className="text-xs font-medium">
                  Sign in
                </Button>
              </Link>
              <Link to="/signup">
                <Button variant="primary" size="sm" id="nav-signup-btn" className="text-xs font-medium">
                  Create account
                </Button>
              </Link>
            </div>
          )}
        </div>
      </nav>

      {/* Mobile Slide-down Menu Drawer */}
      {isMobileMenuOpen && (
        <div className="md:hidden border-t border-zinc-200/80 bg-[#fdf8f8] px-4 py-4 shadow-xl flex flex-col gap-3 animate-in fade-in slide-in-from-top-2">
          {isAuthenticated && user ? (
            <>
              <div className="flex items-center justify-between pb-3 border-b border-outline-variant/60">
                <div className="flex flex-col">
                  <span className="text-sm font-semibold text-primary">{user?.name}</span>
                  <span className="text-xs text-on-surface-variant">{user?.email}</span>
                </div>
                <Badge variant={getRoleBadgeVariant(user?.role)} size="sm">
                  {user?.role}
                </Badge>
              </div>

              <div className="flex flex-col gap-1">
                <Link
                  to="/dashboard"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`p-2.5 rounded-xl text-sm font-medium flex items-center gap-2.5 transition-colors ${
                    isActiveLink('/dashboard')
                      ? 'bg-surface-container-high text-primary font-bold'
                      : 'text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  <Icon name="dashboard" size={18} />
                  Dashboard
                </Link>

                <Link
                  to="/exams"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`p-2.5 rounded-xl text-sm font-medium flex items-center gap-2.5 transition-colors ${
                    isActiveLink('/exams')
                      ? 'bg-surface-container-high text-primary font-bold'
                      : 'text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  <Icon name="assignment" size={18} />
                  Assessments
                </Link>

                {user?.role === 'admin' && (
                  <Link
                    to="/admin/exams"
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={`p-2.5 rounded-xl text-sm font-medium flex items-center gap-2.5 transition-colors ${
                      isActiveLink('/admin/exams')
                        ? 'bg-surface-container-high text-primary font-bold'
                        : 'text-on-surface-variant hover:bg-surface-container'
                    }`}
                  >
                    <Icon name="tune" size={18} />
                    Console
                  </Link>
                )}

                <Link
                  to="/about"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`p-2.5 rounded-xl text-sm font-medium flex items-center gap-2.5 transition-colors ${
                    isActiveLink('/about')
                      ? 'bg-surface-container-high text-primary font-bold'
                      : 'text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  <Icon name="info" size={18} />
                  About
                </Link>

                <Link
                  to="/help"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`p-2.5 rounded-xl text-sm font-medium flex items-center gap-2.5 transition-colors ${
                    isActiveLink('/help')
                      ? 'bg-surface-container-high text-primary font-bold'
                      : 'text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  <Icon name="help" size={18} />
                  Help
                </Link>

                <Link
                  to="/settings"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`p-2.5 rounded-xl text-sm font-medium flex items-center gap-2.5 transition-colors ${
                    isActiveLink('/settings')
                      ? 'bg-surface-container-high text-primary font-bold'
                      : 'text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  <Icon name="settings" size={18} />
                  Settings
                </Link>

                <Link
                  to="/privacy"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`p-2.5 rounded-xl text-sm font-medium flex items-center gap-2.5 transition-colors ${
                    isActiveLink('/privacy')
                      ? 'bg-surface-container-high text-primary font-bold'
                      : 'text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  <Icon name="shield" size={18} />
                  Privacy Policy
                </Link>
              </div>

              <div className="pt-2 border-t border-outline-variant/60">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleLogout}
                  className="w-full justify-center text-xs"
                  icon="logout"
                >
                  Log out
                </Button>
              </div>
            </>
          ) : (
            <div className="flex flex-col gap-2">
              <Link
                to="/about"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2.5 rounded-xl text-sm font-medium text-primary hover:bg-surface-container flex items-center gap-2"
              >
                <Icon name="info" size={18} />
                About
              </Link>
              <Link
                to="/privacy"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2.5 rounded-xl text-sm font-medium text-primary hover:bg-surface-container flex items-center gap-2"
              >
                <Icon name="shield" size={18} />
                Privacy Policy
              </Link>
              <div className="pt-2 border-t border-outline-variant/60 flex flex-col gap-2">
                <Link to="/login" onClick={() => setIsMobileMenuOpen(false)}>
                  <Button variant="secondary" size="sm" className="w-full text-xs">
                    Sign in
                  </Button>
                </Link>
                <Link to="/signup" onClick={() => setIsMobileMenuOpen(false)}>
                  <Button variant="primary" size="sm" className="w-full text-xs">
                    Create account
                  </Button>
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </header>
  );
};
