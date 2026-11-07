! integrator.F90 -- one forward-Euler step of the Gray-Scott system.
subroutine advance(cfg, dt)
   use kinds, only: rk
   use config, only: config_t
   use grid, only: g
   use reaction, only: react_u, react_v
   implicit none
   type(config_t), intent(in) :: cfg
   real(rk), intent(in) :: dt
   integer :: nx, ny

   nx = g%nx
   ny = g%ny
   call apply_bc(g%u, nx, ny, cfg%bc_y)
   call apply_bc(g%v, nx, ny, cfg%bc_y)
   call laplacian(g%lu, g%u, nx, ny, g%dx, g%dy)
   call laplacian(g%lv, g%v, nx, ny, g%dx, g%dy)
   g%u(1:nx, 1:ny) = g%u(1:nx, 1:ny)+dt*(cfg%du*g%lu(1:nx, 1:ny) &
                                         +react_u(g%u(1:nx, 1:ny), g%v(1:nx, 1:ny), cfg%feed))
   g%v(1:nx, 1:ny) = g%v(1:nx, 1:ny)+dt*(cfg%dv*g%lv(1:nx, 1:ny) &
                                         +react_v(g%u(1:nx, 1:ny), g%v(1:nx, 1:ny), cfg%feed, cfg%kill))
   where (g%v < 0.0_rk) g%v = 0.0_rk
end subroutine advance
