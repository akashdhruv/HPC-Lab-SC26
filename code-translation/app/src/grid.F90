! grid.F90 -- the mesh and its fields u, v and their Laplacians, with one guard layer.
module grid
   use kinds, only: rk
   use config, only: config_t
   implicit none

   type :: grid_t
      integer :: nx = 0, ny = 0
      real(rk) :: dx = 0, dy = 0
      real(rk), allocatable, dimension(:, :) :: u, v, lu, lv
   end type grid_t

   type(grid_t), target :: g

contains

   subroutine grid_init(cfg)
      type(config_t), intent(in) :: cfg
      g%nx = cfg%nx
      g%ny = cfg%ny
      g%dx = cfg%lx/real(cfg%nx, rk)
      g%dy = cfg%ly/real(cfg%ny, rk)
      allocate (g%u(0:g%nx+1, 0:g%ny+1), g%v(0:g%nx+1, 0:g%ny+1))
      allocate (g%lu(0:g%nx+1, 0:g%ny+1), g%lv(0:g%nx+1, 0:g%ny+1))
      g%u = 1.0_rk
      g%v = 0.0_rk
      g%lu = 0.0_rk
      g%lv = 0.0_rk
   end subroutine grid_init

   subroutine grid_free()
      deallocate (g%u, g%v, g%lu, g%lv)
   end subroutine grid_free

end module grid
