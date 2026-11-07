! config.F90 -- run parameters, read from a namelist file with defaults.
module config
   use kinds, only: rk
   implicit none

   type :: config_t
      integer :: nx = 64, ny = 64, nsteps = 1000, interval = 100, seed = 1
      real(rk) :: lx = 64.0_rk, ly = 64.0_rk
      real(rk) :: du = 0.16_rk, dv = 0.08_rk, feed = 0.035_rk, kill = 0.065_rk, cfl = 0.8_rk
      character(len=16) :: bc_y = 'periodic'
   end type config_t

contains

   subroutine read_config(cfg, path)
      type(config_t), intent(out) :: cfg
      character(len=*), intent(in) :: path
      integer :: nx, ny, nsteps, interval, seed, unit, ios
      real(rk) :: lx, ly, du, dv, feed, kill, cfl
      character(len=16) :: bc_y
      namelist /rd/ nx, ny, lx, ly, du, dv, feed, kill, cfl, nsteps, interval, bc_y, seed

      nx = cfg%nx; ny = cfg%ny; lx = cfg%lx; ly = cfg%ly; du = cfg%du; dv = cfg%dv
      feed = cfg%feed; kill = cfg%kill; cfl = cfg%cfl; nsteps = cfg%nsteps
      interval = cfg%interval; bc_y = cfg%bc_y; seed = cfg%seed

      open (newunit=unit, file=path, status='old', action='read', iostat=ios)
      if (ios == 0) then
         read (unit, nml=rd)
         close (unit)
      else
         print *, "config: ", trim(path), " not found, using defaults"
      end if

      cfg = config_t(nx, ny, nsteps, interval, seed, lx, ly, du, dv, feed, kill, cfl, bc_y)
      print '(A,I0,A,I0,A,A)', " config: ", cfg%nx, " x ", cfg%ny, ", bc_y = ", trim(cfg%bc_y)
   end subroutine read_config

end module config
